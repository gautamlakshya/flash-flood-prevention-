from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..models.database import RainfallRecord, LiveAlertEvent, ProviderHealth

class RiskEvaluationResult(BaseModel):
    alert_type: str = "LIVE"  # LIVE, SIMULATION, or TEST
    severity: str             # NORMAL, WATCH, WARNING, CRITICAL, STALE, UNKNOWN
    zone: str = "Chungthang Basin (Teesta River)"
    headline: str
    description: str
    trigger_rule: str
    trigger_inputs: Dict[str, Any]
    threshold_config: Dict[str, Any]
    predicted_discharge: Optional[float] = None
    threshold_value: Optional[float] = None
    threshold_name: Optional[str] = None
    data_freshness_minutes: Optional[float] = None
    status: str = "ACTIVE"
    evaluation_time: datetime
    should_notify: bool
    is_escalation: bool
    is_resolution: bool
    alert_event_id: Optional[str] = None
    disclaimer: str = (
        "Uncalibrated prototype demonstration thresholds. "
        "Intended for operational architecture testing, not official life-safety warnings."
    )

class RainfallRiskEvaluator:
    """
    Deterministic risk evaluator for flash flood hazard in the Chungthang basin.
    Evaluates both:
    1. Persisted real Open-Meteo precipitation telemetry.
    2. Hydrological discharge predictions (ST-GNN / PINN outputs).

    Applies data freshness validation, hysteresis, escalation, and deduplication.
    """

    DEFAULT_THRESHOLDS = {
        "1h": {"watch": 15.0, "warning": 30.0, "critical": 50.0},
        "3h": {"watch": 30.0, "warning": 60.0, "critical": 90.0},
        "6h": {"watch": 45.0, "warning": 80.0, "critical": 120.0},
        "24h": {"watch": 60.0, "warning": 120.0, "critical": 180.0}
    }

    SEVERITY_ORDER = {
        "UNKNOWN": -1,
        "STALE": -1,
        "NORMAL": 0,
        "WATCH": 1,
        "WARNING": 2,
        "CRITICAL": 3
    }

    def __init__(
        self,
        thresholds: Optional[Dict[str, Dict[str, float]]] = None,
        stale_threshold_minutes: Optional[int] = None,
        cooldown_minutes: Optional[int] = None,
        zone: str = "Chungthang Basin (Teesta River)"
    ):
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self.stale_threshold_minutes = stale_threshold_minutes or settings.RAINFALL_STALE_THRESHOLD_MINUTES
        self.cooldown_minutes = cooldown_minutes or settings.ALERT_COOLDOWN_MINUTES
        self.zone = zone

    def evaluate(self, db: Session, now: Optional[datetime] = None) -> RiskEvaluationResult:
        """
        Evaluates current rainfall risk from persisted RainfallRecord data.
        """
        now_utc = now or datetime.now(timezone.utc)
        now_naive = now_utc.astimezone(timezone.utc).replace(tzinfo=None)

        # 1. Fetch recent records up to current window + 48 hours back
        lookback_start = now_naive - timedelta(hours=48)
        records = db.query(RainfallRecord).filter(
            RainfallRecord.source == "OPEN_METEO",
            RainfallRecord.valid_time >= lookback_start
        ).order_by(RainfallRecord.valid_time.asc()).all()

        # Edge case: No data in database
        if not records:
            return RiskEvaluationResult(
                alert_type="LIVE",
                severity="UNKNOWN",
                zone=self.zone,
                headline="Rainfall Telemetry Unavailable",
                description="No persisted Open-Meteo precipitation records found for Chungthang.",
                trigger_rule="NO_DATA",
                trigger_inputs={"record_count": 0, "freshness_minutes": None},
                threshold_config=self.thresholds,
                data_freshness_minutes=None,
                status="EXPIRED",
                evaluation_time=now_utc,
                should_notify=False,
                is_escalation=False,
                is_resolution=False
            )

        # 2. Check Freshness of latest data
        latest_record = max(records, key=lambda r: r.valid_time)
        retrieval_times = [r.retrieval_time for r in records if r.retrieval_time]
        latest_retrieval = max(retrieval_times) if retrieval_times else latest_record.valid_time

        freshness_minutes = (now_naive - latest_retrieval).total_seconds() / 60.0

        # If retrieval is older than stale threshold, mark STALE (honest state, not false NORMAL)
        if freshness_minutes > self.stale_threshold_minutes:
            return RiskEvaluationResult(
                alert_type="LIVE",
                severity="STALE",
                zone=self.zone,
                headline="Rainfall Telemetry Stale",
                description=(
                    f"Rainfall data was last retrieved {freshness_minutes:.0f} minutes ago, "
                    f"exceeding stale limit ({self.stale_threshold_minutes}m). "
                    "Risk classification cannot guarantee safety until telemetry syncs."
                ),
                trigger_rule="DATA_STALE",
                trigger_inputs={
                    "freshness_minutes": round(freshness_minutes, 1),
                    "stale_threshold_minutes": self.stale_threshold_minutes,
                    "latest_retrieval": latest_retrieval.isoformat()
                },
                threshold_config=self.thresholds,
                data_freshness_minutes=round(freshness_minutes, 1),
                status="ACTIVE",
                evaluation_time=now_utc,
                should_notify=False,
                is_escalation=False,
                is_resolution=False
            )

        # 3. Compute rolling windows: 1h, 3h, 6h, 24h
        anchor_time = min(now_naive, latest_record.valid_time)

        def sum_in_window(hours: int) -> float:
            start_w = anchor_time - timedelta(hours=hours)
            return sum(
                r.precipitation_mm for r in records
                if start_w < r.valid_time <= anchor_time
            )

        p_1h = sum_in_window(1)
        p_3h = sum_in_window(3)
        p_6h = sum_in_window(6)
        p_24h = sum_in_window(24)

        trigger_inputs = {
            "p_1h_mm": round(p_1h, 2),
            "p_3h_mm": round(p_3h, 2),
            "p_6h_mm": round(p_6h, 2),
            "p_24h_mm": round(p_24h, 2),
            "anchor_time": anchor_time.isoformat(),
            "latest_record_time": latest_record.valid_time.isoformat(),
            "freshness_minutes": round(freshness_minutes, 1)
        }

        # 4. Deterministic Threshold Evaluation
        candidate_severity = "NORMAL"
        trigger_rule = "All accumulations below Watch threshold"
        th_val = 0.0
        th_name = "None"

        # Check critical
        if p_1h >= self.thresholds["1h"]["critical"]:
            candidate_severity = "CRITICAL"
            th_val = self.thresholds["1h"]["critical"]
            th_name = "1h Rainfall Critical"
            trigger_rule = f"1h rain {p_1h:.1f}mm >= Critical ({th_val}mm)"
        elif p_3h >= self.thresholds["3h"]["critical"]:
            candidate_severity = "CRITICAL"
            th_val = self.thresholds["3h"]["critical"]
            th_name = "3h Rainfall Critical"
            trigger_rule = f"3h rain {p_3h:.1f}mm >= Critical ({th_val}mm)"
        elif p_6h >= self.thresholds["6h"]["critical"]:
            candidate_severity = "CRITICAL"
            th_val = self.thresholds["6h"]["critical"]
            th_name = "6h Rainfall Critical"
            trigger_rule = f"6h rain {p_6h:.1f}mm >= Critical ({th_val}mm)"
        elif p_24h >= self.thresholds["24h"]["critical"]:
            candidate_severity = "CRITICAL"
            th_val = self.thresholds["24h"]["critical"]
            th_name = "24h Rainfall Critical"
            trigger_rule = f"24h rain {p_24h:.1f}mm >= Critical ({th_val}mm)"
        # Check warning
        elif p_1h >= self.thresholds["1h"]["warning"]:
            candidate_severity = "WARNING"
            th_val = self.thresholds["1h"]["warning"]
            th_name = "1h Rainfall Warning"
            trigger_rule = f"1h rain {p_1h:.1f}mm >= Warning ({th_val}mm)"
        elif p_3h >= self.thresholds["3h"]["warning"]:
            candidate_severity = "WARNING"
            th_val = self.thresholds["3h"]["warning"]
            th_name = "3h Rainfall Warning"
            trigger_rule = f"3h rain {p_3h:.1f}mm >= Warning ({th_val}mm)"
        elif p_6h >= self.thresholds["6h"]["warning"]:
            candidate_severity = "WARNING"
            th_val = self.thresholds["6h"]["warning"]
            th_name = "6h Rainfall Warning"
            trigger_rule = f"6h rain {p_6h:.1f}mm >= Warning ({th_val}mm)"
        elif p_24h >= self.thresholds["24h"]["warning"]:
            candidate_severity = "WARNING"
            th_val = self.thresholds["24h"]["warning"]
            th_name = "24h Rainfall Warning"
            trigger_rule = f"24h rain {p_24h:.1f}mm >= Warning ({th_val}mm)"
        # Check watch
        elif p_1h >= self.thresholds["1h"]["watch"]:
            candidate_severity = "WATCH"
            th_val = self.thresholds["1h"]["watch"]
            th_name = "1h Rainfall Watch"
            trigger_rule = f"1h rain {p_1h:.1f}mm >= Watch ({th_val}mm)"
        elif p_3h >= self.thresholds["3h"]["watch"]:
            candidate_severity = "WATCH"
            th_val = self.thresholds["3h"]["watch"]
            th_name = "3h Rainfall Watch"
            trigger_rule = f"3h rain {p_3h:.1f}mm >= Watch ({th_val}mm)"
        elif p_6h >= self.thresholds["6h"]["watch"]:
            candidate_severity = "WATCH"
            th_val = self.thresholds["6h"]["watch"]
            th_name = "6h Rainfall Watch"
            trigger_rule = f"6h rain {p_6h:.1f}mm >= Watch ({th_val}mm)"
        elif p_24h >= self.thresholds["24h"]["watch"]:
            candidate_severity = "WATCH"
            th_val = self.thresholds["24h"]["watch"]
            th_name = "24h Rainfall Watch"
            trigger_rule = f"24h rain {p_24h:.1f}mm >= Watch ({th_val}mm)"

        # 5. Hysteresis, Escalation, Deduplication & Resolution
        # Determine alert_type based on whether input data is real observation vs forecast
        has_obs = any(r.data_type == "OBSERVATION" for r in records)
        eval_alert_type = "LIVE" if has_obs else "FORECAST"

        last_alert = db.query(LiveAlertEvent).filter(
            LiveAlertEvent.alert_type.in_([eval_alert_type, "LIVE", "FORECAST"])
        ).order_by(LiveAlertEvent.created_at.desc()).first()

        prev_severity = last_alert.severity if last_alert else "NORMAL"
        prev_rank = self.SEVERITY_ORDER.get(prev_severity, 0)
        curr_rank = self.SEVERITY_ORDER.get(candidate_severity, 0)

        should_notify = False
        is_escalation = False
        is_resolution = False

        if curr_rank > prev_rank:
            if candidate_severity in ("WATCH", "WARNING", "CRITICAL"):
                should_notify = True
                is_escalation = True
        elif curr_rank == prev_rank and candidate_severity in ("WARNING", "CRITICAL"):
            if last_alert:
                age_since_last_alert = (now_naive - last_alert.created_at).total_seconds() / 60.0
                should_notify = age_since_last_alert > self.cooldown_minutes
            else:
                should_notify = True
        elif curr_rank < prev_rank:
            if prev_severity in ("WARNING", "CRITICAL") and candidate_severity in ("NORMAL", "WATCH"):
                is_resolution = True
                should_notify = True
                if last_alert and last_alert.is_active:
                    last_alert.is_active = False
                    last_alert.status = "RESOLVED"
                    last_alert.resolved_at = now_naive

        type_label = "FORECAST" if eval_alert_type == "FORECAST" else "LIVE"
        if candidate_severity == "CRITICAL":
            headline = f"CRITICAL FLASH FLOOD WARNING ({type_label}): {self.zone}"
            description = (
                f"Severe precipitation event detected. {trigger_rule}. "
                f"Immediate flood threat along the Teesta corridor."
            )
        elif candidate_severity == "WARNING":
            headline = f"FLASH FLOOD WARNING ({type_label}): {self.zone}"
            description = (
                f"Significant rainfall accumulation. {trigger_rule}. "
                f"Water levels expected to surge. Prepare flood response."
            )
        elif candidate_severity == "WATCH":
            headline = f"FLOOD WATCH ({type_label}): {self.zone}"
            description = (
                f"Moderate rainfall threshold exceeded. {trigger_rule}. "
                f"Monitoring Teesta upstream conditions."
            )
        else:
            if is_resolution:
                headline = f"FLOOD ALERT RESOLVED ({type_label}): {self.zone}"
                description = f"Precipitation has receded below alert thresholds in Chungthang. {trigger_rule}."
            else:
                headline = f"NORMAL ({type_label}): {self.zone}"
                description = "All rainfall accumulations in Chungthang basin remain within normal baseline limits."

        return RiskEvaluationResult(
            alert_type=eval_alert_type,
            severity=candidate_severity,
            zone=self.zone,
            headline=headline,
            description=description,
            trigger_rule=trigger_rule,
            trigger_inputs=trigger_inputs,
            threshold_config=self.thresholds,
            threshold_value=th_val,
            threshold_name=th_name,
            data_freshness_minutes=round(freshness_minutes, 1),
            status="RESOLVED" if is_resolution else ("ACTIVE" if candidate_severity != "NORMAL" else "RESOLVED"),
            evaluation_time=now_utc,
            should_notify=should_notify,
            is_escalation=is_escalation,
            is_resolution=is_resolution
        )

    def evaluate_prediction(
        self,
        predicted_discharge: float,
        bankfull_capacity: float = 900.0,
        rate_of_rise: float = 0.0,
        is_simulation: bool = True,
        data_freshness_minutes: float = 0.0,
        db: Optional[Session] = None
    ) -> RiskEvaluationResult:
        """
        Evaluates risk from hydrodynamic predictions (discharge vs channel capacity).
        Explicitly flags simulation runs as SIMULATION alerts.
        """
        now_utc = datetime.now(timezone.utc)
        now_naive = now_utc.astimezone(timezone.utc).replace(tzinfo=None)

        alert_type = "SIMULATION" if is_simulation else "LIVE"
        utilization = (predicted_discharge / bankfull_capacity) * 100.0 if bankfull_capacity > 0 else 0.0

        if predicted_discharge >= (1.5 * bankfull_capacity):
            severity = "CRITICAL"
            headline = f"CRITICAL FLASH FLOOD WARNING ({alert_type})"
            rule = f"Predicted Q {predicted_discharge:.1f} m³/s exceeds 150% bankfull capacity ({bankfull_capacity} m³/s)"
        elif predicted_discharge >= bankfull_capacity or utilization >= 100.0:
            severity = "WARNING"
            headline = f"FLASH FLOOD WARNING ({alert_type})"
            rule = f"Predicted Q {predicted_discharge:.1f} m³/s exceeds Qcrit threshold ({bankfull_capacity} m³/s)"
        elif utilization >= 80.0 or (rate_of_rise >= 1.5 and utilization >= 70.0):
            severity = "WATCH"
            headline = f"FLOOD WATCH ({alert_type})"
            rule = f"Capacity utilization {utilization:.1f}% approaching limit (dQ/dt={rate_of_rise:.2f} m³/s²)"
        else:
            severity = "NORMAL"
            headline = f"NORMAL ({alert_type})"
            rule = f"Discharge {predicted_discharge:.1f} m³/s well within safe capacity ({bankfull_capacity} m³/s)"

        description = (
            f"Hydrological model indicates {severity} hazard level for {self.zone}. "
            f"Capacity utilization is {utilization:.1f}%."
        )

        return RiskEvaluationResult(
            alert_type=alert_type,
            severity=severity,
            zone=self.zone,
            headline=headline,
            description=description,
            trigger_rule=rule,
            trigger_inputs={
                "predicted_discharge": round(predicted_discharge, 1),
                "bankfull_capacity": bankfull_capacity,
                "capacity_utilization": round(utilization, 1),
                "rate_of_rise": round(rate_of_rise, 3),
                "is_simulation": is_simulation
            },
            threshold_config={"bankfull_capacity_qcrit": bankfull_capacity},
            predicted_discharge=round(predicted_discharge, 1),
            threshold_value=bankfull_capacity,
            threshold_name="Bankfull Discharge Qcrit (Uncalibrated Prototype)",
            data_freshness_minutes=round(data_freshness_minutes, 1),
            status="ACTIVE" if severity != "NORMAL" else "RESOLVED",
            evaluation_time=now_utc,
            should_notify=(severity in ("WARNING", "CRITICAL")),
            is_escalation=False,
            is_resolution=False
        )

