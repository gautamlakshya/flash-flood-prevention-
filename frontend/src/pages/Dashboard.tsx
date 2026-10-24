import { useEffect, useState } from 'react';
import { useAppStore } from '../stores/appStore';
import FloodMap from '../map/FloodMap';
import { CloudRain, RefreshCw } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';

interface RealRainfallData {
  status: string;
  source: string;
  data_type: string;
  is_forecast: boolean;
  coordinates: { latitude: number; longitude: number };
  latest_reading: {
    valid_time: string;
    retrieval_time: string | null;
    precipitation_mm: number;
    units: string;
  } | null;
  rolling_accumulations: {
    "1h_mm": number;
    "3h_mm": number;
    "6h_mm": number;
    "24h_mm": number;
  };
  freshness_minutes: number | null;
  is_fresh: boolean;
  provider_status: string;
  disclaimer: string;
}

export default function Dashboard() {
  const { result, simulationStatus, isSimulating, dataMode } = useAppStore();
  const isWarning = result?.metrics?.hazard === 'FLASH FLOOD WARNING';

  const [rainfallData, setRainfallData] = useState<RealRainfallData | null>(null);
  const [activeAlert, setActiveAlert] = useState<any>(null);
  const [ingesting, setIngesting] = useState(false);
  const [ingestMessage, setIngestMessage] = useState<string | null>(null);

  const apiUrl = ((import.meta as any).env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

  const fetchActiveAlert = () => {
    fetch(`${apiUrl}/api/v1/alerts/active`)
      .then(res => res.json())
      .then(data => {
        if (data?.alert) {
          setActiveAlert(data.alert);
        } else {
          setActiveAlert(null);
        }
      })
      .catch(e => {
        console.error("Failed to load active alert:", e);
      });
  };

  const fetchRainfall = () => {
    fetch(`${apiUrl}/api/v1/rainfall/latest`)
      .then(res => res.json())
      .then(data => {
        setRainfallData(data);
      })
      .catch(e => {
        console.error("Failed to load real rainfall telemetry:", e);
      });
  };

  const triggerIngest = () => {
    setIngesting(true);
    setIngestMessage(null);
    fetch(`${apiUrl}/api/v1/rainfall/ingest-and-evaluate`, { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        setIngesting(false);
        if (data.status === 'success') {
          const alertNotice = data.alert?.created ? ` [Alert Generated: ${data.alert.severity}]` : '';
          const pushNotice = data.notifications?.WEB_PUSH?.[0]?.status === 'SENT' ? ' [Push Dispatched]' : '';
          setIngestMessage(`Synced: ${data.evaluation.severity} (${data.ingestion.records_fetched} records)${alertNotice}${pushNotice}`);
          fetchRainfall();
          fetchActiveAlert();
        } else {
          setIngestMessage(`Notice: ${data.detail || 'Completed'}`);
        }
      })
      .catch(e => {
        setIngesting(false);
        setIngestMessage(`Sync failed: ${e.message}`);
      });
  };

  useEffect(() => {
    fetchRainfall();
    fetchActiveAlert();
    const interval = setInterval(() => {
      fetchRainfall();
      fetchActiveAlert();
    }, 60000); // Poll status every minute
    return () => clearInterval(interval);
  }, []);

  const formatChartData = () => {
    if (!result || !result.timeseries) return [];

    return result.timeseries.map((t, idx) => {
      const q = t.runoff_volume_m3 / 900;
      return {
        time: t.timestamp ? new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : `T+${idx * 15}m`,
        discharge: Math.round(q * 10) / 10,
        predicted: idx === result.timeseries.length - 1 ? result.metrics.predicted_discharge : null
      };
    });
  };

  const chartData = formatChartData();
  const effectiveWarning = isWarning || activeAlert?.severity === 'WARNING' || activeAlert?.severity === 'CRITICAL';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', padding: '16px' }}>

      {/* 1. COMPACT REAL TELEMETRY SUMMARY (FULL-WIDTH) */}
      <div className="card" style={{
        padding: '12px 18px',
        background: 'linear-gradient(135deg, rgba(21, 26, 39, 0.95) 0%, rgba(26, 34, 52, 0.85) 100%)',
        border: '1px solid #334155',
        borderRadius: '8px'
      }}>
        <div className="flex justify-between items-center flex-wrap" style={{ gap: '12px' }}>
          {/* Source branding & metadata */}
          <div className="flex items-center gap-3">
            <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(56, 189, 248, 0.1)', color: '#38BDF8', display: 'flex', alignItems: 'center' }}>
              <CloudRain size={22} />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span style={{ fontWeight: 700, fontSize: '0.95rem', letterSpacing: '0.2px' }}>
                  REAL TELEMETRY: Open-Meteo Forecast NWP (Chungthang Basin)
                </span>
                <span style={{ fontSize: '0.65rem', padding: '2px 6px', borderRadius: '4px', background: '#0369A1', color: '#FFF', fontWeight: 600 }}>
                  FORECAST MODEL (NWP)
                </span>
                {rainfallData && (
                  <span className={`alert-badge ${rainfallData.is_fresh ? 'alert-normal' : 'alert-watch'}`} style={{ fontSize: '0.65rem', padding: '2px 8px' }}>
                    {rainfallData.is_fresh ? 'FRESH DATA' : 'STALE TELEMETRY'}
                  </span>
                )}
              </div>
              <div className="text-muted" style={{ fontSize: '0.75rem', marginTop: '2px' }}>
                Coordinates: 27.6033°N, 88.6475°E | Model: ECMWF/GFS Ensemble | Units: mm
                {rainfallData?.latest_reading?.valid_time && (
                  <span style={{ color: '#CBD5E1' }}> | Latest Valid: {new Date(rainfallData.latest_reading.valid_time).toUTCString()}</span>
                )}
              </div>
            </div>
          </div>

          {/* Quick Metrics & Sync Trigger */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <div style={{ textAlign: 'center', padding: '4px 10px', background: 'var(--bg-main)', border: '1px solid #1E293B', borderRadius: '6px' }}>
                <div className="text-muted" style={{ fontSize: '0.65rem' }}>1-Hour Rain</div>
                <div style={{ fontWeight: 700, fontSize: '1rem', color: '#38BDF8' }}>
                  {rainfallData ? `${rainfallData.rolling_accumulations["1h_mm"]} mm` : '--'}
                </div>
              </div>
              <div style={{ textAlign: 'center', padding: '4px 10px', background: 'var(--bg-main)', border: '1px solid #1E293B', borderRadius: '6px' }}>
                <div className="text-muted" style={{ fontSize: '0.65rem' }}>3-Hour Rain</div>
                <div style={{ fontWeight: 700, fontSize: '1rem', color: '#38BDF8' }}>
                  {rainfallData ? `${rainfallData.rolling_accumulations["3h_mm"]} mm` : '--'}
                </div>
              </div>
              <div style={{ textAlign: 'center', padding: '4px 10px', background: 'var(--bg-main)', border: '1px solid #1E293B', borderRadius: '6px' }}>
                <div className="text-muted" style={{ fontSize: '0.65rem' }}>24-Hour Rain</div>
                <div style={{ fontWeight: 700, fontSize: '1rem', color: '#38BDF8' }}>
                  {rainfallData ? `${rainfallData.rolling_accumulations["24h_mm"]} mm` : '--'}
                </div>
              </div>
              <div style={{ textAlign: 'center', padding: '4px 10px', background: 'var(--bg-main)', border: '1px solid #1E293B', borderRadius: '6px' }}>
                <div className="text-muted" style={{ fontSize: '0.65rem' }}>Data Age</div>
                <div style={{ fontWeight: 600, fontSize: '0.85rem', color: rainfallData?.is_fresh ? 'var(--status-normal)' : 'var(--status-watch)' }}>
                  {rainfallData?.freshness_minutes !== null && rainfallData?.freshness_minutes !== undefined
                    ? `${rainfallData.freshness_minutes.toFixed(0)}m ago`
                    : 'Awaiting sync'}
                </div>
              </div>
            </div>

            <button
              className="btn btn-primary"
              onClick={triggerIngest}
              disabled={ingesting}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', padding: '6px 14px' }}
            >
              <RefreshCw size={13} className={ingesting ? "animate-spin" : ""} />
              {ingesting ? 'Syncing...' : 'Sync & Evaluate'}
            </button>
          </div>
        </div>

        {ingestMessage && (
          <div style={{ marginTop: '8px', fontSize: '0.75rem', color: '#38BDF8', borderTop: '1px solid #1E293B', paddingTop: '6px' }}>
            ℹ️ {ingestMessage}
          </div>
        )}
      </div>

      {/* 2. PRIMARY WORKSPACE: MAP (DOMINANT) + EVENT STATUS */}
      <div className="dashboard-grid-primary">
        {/* Map Container */}
        <div style={{
          height: '540px',
          minHeight: '460px',
          borderRadius: 'var(--border-radius)',
          overflow: 'hidden',
          border: '1px solid var(--border-color)',
          position: 'relative',
          boxShadow: 'var(--shadow-md)',
          background: '#0B0F19'
        }}>
          <FloodMap
            isWarning={effectiveWarning}
            inundationGeoJSON={result?.inundation_geojson}
            activeAlert={activeAlert}
            rainfallData={rainfallData}
          />
        </div>

        {/* Event Status Panel */}
        <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', height: '540px', overflowY: 'auto' }}>
          <div className="card-header" style={{ marginBottom: 0, paddingBottom: '10px' }}>
            <span className="card-title" style={{ fontSize: '0.85rem' }}>Event Status</span>
            {result?.metrics?.hazard === 'NOT_CONFIGURED' ? (
              <span className="alert-badge" style={{ backgroundColor: '#475569', fontSize: '0.7rem' }}>WAITING FOR REAL DATA</span>
            ) : isWarning ? (
              <span className="alert-badge alert-warning animate-in" style={{ fontSize: '0.7rem' }}>FLASH FLOOD WARNING (SIM)</span>
            ) : result ? (
              <span className="alert-badge alert-normal" style={{ fontSize: '0.7rem' }}>{result.metrics.hazard || 'NORMAL'}</span>
            ) : activeAlert ? (
              <span className={`alert-badge ${activeAlert.severity === 'CRITICAL' || activeAlert.severity === 'WARNING' ? 'alert-warning' : (activeAlert.severity === 'WATCH' ? 'alert-watch' : 'alert-normal')} animate-in`} style={{ fontSize: '0.7rem' }}>
                {activeAlert.severity} ({activeAlert.alert_type || 'FORECAST'})
              </span>
            ) : (
              <span className="alert-badge alert-normal" style={{ fontSize: '0.7rem' }}>SYSTEM READY (IDLE)</span>
            )}
          </div>

          {/* Peak discharge */}
          <div className="stat-box" style={{ padding: '10px 14px' }}>
            <span className="stat-label" style={{ fontSize: '0.72rem' }}>Predicted Peak Discharge (Chungthang Outlet)</span>
            {isSimulating ? (
              <span className="stat-value" style={{ fontSize: '1.25rem', color: 'var(--accent-primary)' }}>COMPUTING...</span>
            ) : !result ? (
              <span className="stat-value" style={{ fontSize: '1.15rem', color: '#94A3B8' }}>READY TO SIMULATE</span>
            ) : result.metrics.predicted_discharge === 'NOT_CONFIGURED' ? (
              <span className="stat-value" style={{ fontSize: '1rem', color: '#94A3B8' }}>NOT CONFIGURED</span>
            ) : (
              <span className="stat-value" style={{ fontSize: '1.35rem', color: isWarning ? 'var(--status-warning)' : 'var(--text-main)' }}>
                {result.metrics.predicted_discharge.toLocaleString()} <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>m³/s</span>
              </span>
            )}
          </div>

          {/* 3 Metric Grid: Qcrit, Stage, dQ/dt */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
            <div className="stat-box" style={{ padding: '8px 6px', textAlign: 'center' }}>
              <span className="stat-label" style={{ fontSize: '0.65rem' }}>Qcrit</span>
              <span style={{ fontWeight: 'bold', fontSize: '0.78rem' }}>
                {result ? (result.metrics.qcrit === 'NOT_CONFIGURED' ? 'N/A' : `${result.metrics.qcrit} m³/s`) : '900 m³/s'}
              </span>
            </div>
            <div className="stat-box" style={{ padding: '8px 6px', textAlign: 'center' }}>
              <span className="stat-label" style={{ fontSize: '0.65rem' }}>Stage</span>
              <span style={{ fontWeight: 'bold', fontSize: '0.78rem' }}>
                {result ? (result.metrics.stage_m === 'NOT_CONFIGURED' ? 'N/A' : `${result.metrics.stage_m} m`) : '0.00 m'}
              </span>
            </div>
            <div className="stat-box" style={{ padding: '8px 6px', textAlign: 'center' }}>
              <span className="stat-label" style={{ fontSize: '0.65rem' }}>dQ/dt</span>
              <span style={{ fontWeight: 'bold', fontSize: '0.78rem' }}>
                {result ? (result.metrics.dq_dt === 'NOT_CONFIGURED' ? 'N/A' : `${result.metrics.dq_dt}`) : '0.000'}
              </span>
            </div>
          </div>

          {/* Capacity Utilization */}
          <div style={{ background: 'var(--bg-main)', padding: '10px 12px', borderRadius: '6px', border: '1px solid #1E293B' }}>
            <div className="flex justify-between" style={{ marginBottom: '6px', fontSize: '0.78rem' }}>
              <span style={{ color: '#94A3B8' }}>Channel Capacity Utilization</span>
              <span className={isWarning ? 'text-warning' : 'text-normal'} style={{ fontWeight: 700 }}>
                {result ? (result.metrics.capacity_utilization === 'NOT_CONFIGURED' || result.metrics.capacity_utilization === 0 ? '0.0%' : `${result.metrics.capacity_utilization}%`) : '0.0%'}
              </span>
            </div>
            <div style={{ height: '6px', background: '#0F172A', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: result && typeof result.metrics.capacity_utilization === 'number' ? `${Math.min(100, result.metrics.capacity_utilization)}%` : '0%',
                background: isWarning ? 'var(--status-warning)' : 'var(--status-normal)',
                transition: 'var(--transition)'
              }} />
            </div>
          </div>

          {/* Operational Context Box */}
          <div className="text-muted" style={{ fontSize: '0.78rem', background: 'var(--bg-main)', padding: '10px 12px', borderRadius: '6px', border: '1px solid #1E293B', display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
            <div>Simulation Status: <strong style={{ color: '#F1F5F9' }}>{simulationStatus}</strong></div>
            <div>Data Mode: <strong className={dataMode === 'SIMULATION' ? 'text-watch' : 'text-normal'}>{dataMode} (PROTOTYPE)</strong></div>
            {activeAlert && !result && (
              <div style={{ marginTop: '4px', paddingTop: '6px', borderTop: '1px solid #334155', color: '#CBD5E1' }}>
                <div>Active Alert: <strong style={{ color: activeAlert.severity === 'CRITICAL' || activeAlert.severity === 'WARNING' ? '#EF4444' : '#38BDF8' }}>{activeAlert.headline}</strong></div>
                <div style={{ fontSize: '0.7rem', marginTop: '2px', color: '#94A3B8' }}>Rule: {activeAlert.trigger_rule}</div>
                <div style={{ fontSize: '0.7rem', marginTop: '1px', color: '#64748B' }}>ID: {activeAlert.id}</div>
              </div>
            )}
            {result?.provenance && (
              <div style={{ marginTop: 'auto', paddingTop: '4px', fontSize: '0.7rem', color: '#64748B', borderTop: '1px solid #1E293B' }}>
                Hydrologic Engine: {result.provenance.model || 'ST-GNN-v1.0'}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 3. SECONDARY INFORMATION: HYDROGRAPH & CATCHMENT SUMMARY */}
      <div className="dashboard-grid-secondary">
        {/* Hydrograph */}
        <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', minHeight: '280px' }}>
          <div className="card-header flex justify-between items-center" style={{ marginBottom: '12px', paddingBottom: '8px' }}>
            <span className="card-title" style={{ fontSize: '0.85rem' }}>Runoff & Discharge Hydrograph</span>
            {result && <span style={{ fontSize: '0.7rem', color: '#F59E0B', fontWeight: 600 }}>SIMULATED SCENARIO</span>}
          </div>
          {result && result.timeseries && result.timeseries.length > 0 ? (
            <div style={{ width: '100%', height: '220px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 25, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="time" stroke="#94A3B8" fontSize={11} />
                  <YAxis stroke="#94A3B8" fontSize={11} label={{ value: 'm³/s', angle: -90, position: 'insideLeft', fill: '#94A3B8', fontSize: 10 }} />
                  <Tooltip contentStyle={{ backgroundColor: '#151A27', borderColor: '#334155', borderRadius: '6px', fontSize: '0.75rem' }} />
                  <Legend wrapperStyle={{ fontSize: '0.75rem' }} />
                  {typeof result.metrics.qcrit === 'number' && (
                    <ReferenceLine y={result.metrics.qcrit} label={{ value: 'Qcrit (900 m³/s)', fill: '#EF4444', fontSize: 10 }} stroke="#EF4444" strokeDasharray="3 3" />
                  )}
                  <Line type="monotone" dataKey="discharge" stroke="#38BDF8" strokeWidth={2} dot={false} name="Runoff Q" />
                  <Line type="monotone" dataKey="predicted" stroke="#F59E0B" strokeWidth={3} dot={{ r: 5 }} name="Predicted Peak Q" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex items-center justify-center text-center" style={{ height: '100%', minHeight: '180px', color: 'var(--text-muted)', fontSize: '0.8rem', padding: '16px' }}>
              {dataMode === 'REAL'
                ? 'WAITING FOR REAL DATA (IMD AWS & CWC Sensors Not Configured)'
                : (isSimulating ? 'Processing simulation pipeline...' : 'Select a scenario in the top header and click "Start Simulation" to generate predictions.')}
            </div>
          )}
        </div>

        {/* Catchment Summary */}
        <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column' }}>
          <div className="card-header" style={{ marginBottom: '12px', paddingBottom: '8px' }}>
            <span className="card-title" style={{ fontSize: '0.85rem' }}>Catchment Summary (Chungthang)</span>
            <span style={{ fontSize: '0.7rem', color: '#38BDF8', fontWeight: 600 }}>~2,969 km²</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.8rem' }}>
            <div className="flex justify-between items-center" style={{ paddingBottom: '6px', borderBottom: '1px solid #1E293B' }}>
              <span style={{ color: '#94A3B8' }}>Peak Runoff Volume</span>
              <span style={{ fontWeight: 700, color: '#F1F5F9' }}>
                {result && result.metrics.peak_runoff_volume !== 'NOT_CONFIGURED' ? `${result.metrics.peak_runoff_volume.toLocaleString()} m³` : 'Ready to compute'}
              </span>
            </div>
            <div className="flex justify-between items-center" style={{ paddingBottom: '6px', borderBottom: '1px solid #1E293B' }}>
              <span style={{ color: '#94A3B8' }}>Soil Moisture (AMC)</span>
              <span style={{ fontWeight: 700, color: '#F1F5F9' }}>{result ? result.metrics.amc : 'AMC-II (Average)'}</span>
            </div>
            <div className="flex justify-between items-center" style={{ paddingBottom: '6px', borderBottom: '1px solid #1E293B' }}>
              <span style={{ color: '#94A3B8' }}>Total Rainfall</span>
              <span style={{ fontWeight: 700, color: '#38BDF8' }}>
                {result && result.timeseries && result.timeseries.length > 0
                  ? `${result.timeseries.reduce((sum, t) => sum + t.rainfall_mm, 0).toFixed(1)} mm`
                  : (rainfallData ? `${rainfallData.rolling_accumulations["24h_mm"]} mm (24h Forecast)` : 'Scenario dependent')}
              </span>
            </div>
            <div className="flex justify-between items-center" style={{ paddingBottom: '6px', borderBottom: '1px solid #1E293B' }}>
              <span style={{ color: '#94A3B8' }}>Basin Drainage</span>
              <span style={{ fontWeight: 600, color: '#CBD5E1', fontSize: '0.75rem' }}>Upper Teesta Corridor</span>
            </div>
            <div style={{ marginTop: 'auto', paddingTop: '6px', fontSize: '0.7rem', color: '#64748B', lineHeight: 1.35 }}>
              Reference CWC Station: 27.5833°N, 88.6475°E (~1,540m)<br/>
              DEM Model Outlet: 27.5851°N, 88.6551°E (~870m snap offset)
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
