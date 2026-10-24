import { useState, useEffect } from 'react';
import { useAppStore } from '../stores/appStore';
import {
  ShieldAlert,
  Code,
  CheckCircle,
  Bell,
  BellOff,
  Send,
  RefreshCw,
  CheckSquare,
  MessageSquare,
  Radio,
  Key,
  Lock
} from 'lucide-react';
import {
  isPushSupported,
  getNotificationPermission,
  checkExistingPushSubscription,
  subscribeToWebPush,
  unsubscribeFromWebPush
} from '../services/webPushService';

interface AlertDelivery {
  id: number;
  channel: string;
  status: string;
  attempt_time: string;
  recipient: string;
  error: string | null;
}

interface AlertRecord {
  id: string;
  alert_type: string;  // LIVE, SIMULATION, TEST
  severity: string;    // NORMAL, WATCH, WARNING, CRITICAL, STALE, UNKNOWN
  zone: string;
  headline: string;
  description: string;
  trigger_rule: string;
  trigger_inputs: any;
  predicted_discharge: number | null;
  threshold_value: number | null;
  threshold_name: string | null;
  data_freshness_minutes: number | null;
  status: string;      // ACTIVE, ACKNOWLEDGED, RESOLVED, EXPIRED
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  acknowledgement_notes: string | null;
  created_at: string;
  resolved_at: string | null;
  is_active: boolean;
  has_cap_xml: boolean;
  cap_xml: string | null;
  deliveries: AlertDelivery[];
}

interface ChannelStatus {
  channel: string;
  status: string;
  configured: boolean;
  enabled: boolean;
  active_subscriptions?: number;
  notes?: string;
  regulatory_framework?: string;
}

export default function ActiveAlerts() {
  const { result } = useAppStore();
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [channels, setChannels] = useState<ChannelStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Web Push state
  const [pushSupported, setPushSupported] = useState(false);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [pushLoading, setPushLoading] = useState(false);
  const [pushFeedback, setPushFeedback] = useState<string | null>(null);

  // Test Notification state
  const [sendingTest, setSendingTest] = useState(false);
  const [testFeedback, setTestFeedback] = useState<{ status: string; message: string } | null>(null);

  // Acknowledgement modal/form state
  const [ackTargetId, setAckTargetId] = useState<string | null>(null);
  const [operatorName, setOperatorName] = useState('');
  const [ackNotes, setAckNotes] = useState('');
  const [acking, setAcking] = useState(false);

  // Selected CAP XML viewer
  const [selectedCapXml, setSelectedCapXml] = useState<{ id: string; xml: string } | null>(null);
  const [showSimCap, setShowSimCap] = useState(false);

  // Operator Authorization Key state (Session-scoped memory, cleared when tab closes)
  const [operatorKey, setOperatorKey] = useState<string>(() => {
    try {
      return sessionStorage.getItem('ffews_operator_key') || '';
    } catch {
      return '';
    }
  });
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [keyInput, setKeyInput] = useState('');
  const [authError, setAuthError] = useState<string | null>(null);

  const saveOperatorKey = (newKey: string) => {
    const trimmed = newKey.trim();
    setOperatorKey(trimmed);
    try {
      if (trimmed) {
        sessionStorage.setItem('ffews_operator_key', trimmed);
      } else {
        sessionStorage.removeItem('ffews_operator_key');
      }
    } catch {
      // SessionStorage unavailable
    }
    setAuthError(null);
  };

  const apiUrl = ((import.meta as any).env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

  const fetchAlertsAndChannels = () => {
    setLoading(true);
    setError(null);

    Promise.all([
      fetch(`${apiUrl}/api/v1/alerts/?limit=50`).then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      }),
      fetch(`${apiUrl}/api/v1/alerts/notification-config`).then(res => res.json()).catch(() => ({ channels: [] }))
    ])
      .then(([alertsData, configData]) => {
        setAlerts(Array.isArray(alertsData) ? alertsData : []);
        setChannels(configData.channels || []);
        setLoading(false);
      })
      .catch(e => {
        console.error("Failed to fetch alerts:", e);
        setError("Unable to reach backend alert service. Displaying local standby registry.");
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchAlertsAndChannels();

    const supported = isPushSupported();
    setPushSupported(supported);
    if (supported) {
      checkExistingPushSubscription().then(sub => {
        setIsSubscribed(!!sub);
      });
    }
  }, []);

  const handleTogglePush = async () => {
    setPushLoading(true);
    setPushFeedback(null);

    if (isSubscribed) {
      const res = await unsubscribeFromWebPush(apiUrl);
      setPushLoading(false);
      if (res.success) {
        setIsSubscribed(false);
        setPushFeedback("Push alerts deactivated for this browser session.");
        fetchAlertsAndChannels();
      } else {
        setPushFeedback(`Error: ${res.message}`);
      }
    } else {
      const res = await subscribeToWebPush(apiUrl);
      setPushLoading(false);
      if (res.success) {
        setIsSubscribed(true);
        setPushFeedback(res.message);
        fetchAlertsAndChannels();
      } else {
        setPushFeedback(res.message);
      }
    }
  };

  const handleSendTestNotification = () => {
    setSendingTest(true);
    setTestFeedback(null);

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (operatorKey) {
      headers['X-Admin-Key'] = operatorKey;
    }

    fetch(`${apiUrl}/api/v1/alerts/test-notification`, {
      method: 'POST',
      headers
    })
      .then(async res => {
        const data = await res.json().catch(() => ({}));
        setSendingTest(false);
        if (res.status === 401) {
          setAuthError('Authentication required: Enter valid Operator Admin Key to dispatch test notifications.');
          setTestFeedback({
            status: 'ERROR',
            message: '🔒 Authentication required: Valid X-Admin-Key required. Click "Operator Auth" above to supply your key.'
          });
          setShowKeyModal(true);
          return;
        }

        if (res.ok) {
          setAuthError(null);
          const pushReport = data.dispatches?.WEB_PUSH?.[0];
          if (pushReport && pushReport.status === 'SENT') {
            setTestFeedback({
              status: 'SUCCESS',
              message: `✅ Test Web Push dispatched to registered browser endpoints!`
            });
          } else if (pushReport && pushReport.status === 'SKIPPED') {
            setTestFeedback({
              status: 'INFO',
              message: `ℹ️ Test notification recorded. Notice: ${pushReport.error || 'No active push subscriptions yet'}. Click 'Enable Browser Push Alerts' above to subscribe this device.`
            });
          } else {
            setTestFeedback({
              status: 'INFO',
              message: `Test alert recorded (ID: ${data.test_event_id}).`
            });
          }
          fetchAlertsAndChannels();
        } else {
          setTestFeedback({
            status: 'ERROR',
            message: data.detail || `Server returned ${res.status}`
          });
        }
      })
      .catch(e => {
        setSendingTest(false);
        setTestFeedback({
          status: 'ERROR',
          message: `Network error: ${e.message}`
        });
      });
  };

  const handleAcknowledgeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ackTargetId || !operatorName.trim()) return;

    setAcking(true);

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (operatorKey) {
      headers['X-Admin-Key'] = operatorKey;
    }

    fetch(`${apiUrl}/api/v1/alerts/${ackTargetId}/acknowledge`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        operator_name: operatorName.trim(),
        notes: ackNotes.trim() || undefined
      })
    })
      .then(async res => {
        setAcking(false);
        if (res.status === 401) {
          setAuthError('Authentication required: Enter valid Operator Admin Key to acknowledge alerts.');
          alert('🔒 Authentication failed: Valid Operator Admin Key required. Please provide your key in the Operator Auth dialog.');
          setShowKeyModal(true);
          return;
        }

        if (res.ok) {
          setAckTargetId(null);
          setOperatorName('');
          setAckNotes('');
          setAuthError(null);
          fetchAlertsAndChannels();
        } else {
          const err = await res.json().catch(() => ({}));
          alert(`Failed to acknowledge alert: ${err.detail || res.statusText}`);
        }
      })
      .catch(e => {
        setAcking(false);
        alert(`Network error: ${e.message}`);
      });
  };

  const isSimWarning = result?.metrics?.hazard === 'FLASH FLOOD WARNING';
  const activeAlerts = alerts.filter(a => a.is_active && a.severity !== 'NORMAL');
  const webPushChannel = channels.find(c => c.channel === 'WEB_PUSH');
  const smsChannel = channels.find(c => c.channel === 'SMS');

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Page Header */}
      <div className="flex items-center justify-between flex-wrap" style={{ gap: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Active Alerts & Multi-Channel Warning Center</h2>
          <p className="text-muted" style={{ fontSize: '0.875rem', marginTop: '4px' }}>
            Lifecycle management, operator acknowledgement, and standards-based browser push alerts for Chungthang, Sikkim
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            className="btn"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              borderColor: operatorKey ? 'var(--status-normal)' : 'var(--border-color)',
              color: operatorKey ? '#34D399' : 'var(--text-muted)'
            }}
            onClick={() => {
              setKeyInput(operatorKey);
              setShowKeyModal(true);
            }}
            title="Configure operator authorization key for current session"
          >
            {operatorKey ? <Lock size={15} /> : <Key size={15} />}
            <span>{operatorKey ? 'Operator Auth: Set' : 'Operator Auth'}</span>
          </button>

          <button className="btn" onClick={fetchAlertsAndChannels} disabled={loading} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Refresh Alerts
          </button>
        </div>
      </div>

      {error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #DC2626', padding: '12px 16px', borderRadius: '8px', color: '#F87171', fontSize: '0.875rem' }}>
          ⚠️ {error}
        </div>
      )}

      {/* Multi-Channel Distribution Infrastructure Panel */}
      <div className="dashboard-grid" style={{ height: 'auto', padding: 0 }}>

        {/* Channel 1: Web Push */}
        <div className="card" style={{ gridColumn: 'span 6', border: '1px solid #334155' }}>
          <div className="card-header flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Radio size={20} className={isSubscribed ? "text-normal" : "text-muted"} />
              <span className="card-title">Browser Web Push (PWA)</span>
            </div>
            <span className={`alert-badge ${isSubscribed ? 'alert-normal' : ''}`} style={!isSubscribed ? { backgroundColor: '#1E293B', color: '#94A3B8' } : {}}>
              {isSubscribed ? 'SUBSCRIBED' : (pushSupported ? 'READY TO SUBSCRIBE' : 'NOT SUPPORTED')}
            </span>
          </div>

          <p className="text-muted" style={{ fontSize: '0.875rem', lineHeight: '1.6' }}>
            Delivers instant push notifications to mobile and desktop devices without requiring third-party messaging apps.
            Uses standards-based Web Push (RFC 8292 VAPID).
          </p>

          <div style={{ marginTop: '12px', fontSize: '0.8rem', color: '#94A3B8' }}>
            Permission Status: <strong>{getNotificationPermission().toUpperCase()}</strong>
            {' '}| Active Subscriptions in Basin: <strong>{webPushChannel?.active_subscriptions ?? 0}</strong>
          </div>

          <div className="flex items-center gap-3 flex-wrap" style={{ marginTop: '16px' }}>
            <button
              className={`btn ${isSubscribed ? '' : 'btn-primary'}`}
              onClick={handleTogglePush}
              disabled={pushLoading || !pushSupported}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem' }}
            >
              {isSubscribed ? <BellOff size={16} /> : <Bell size={16} />}
              {pushLoading ? 'Updating...' : (isSubscribed ? 'Disable Push Alerts' : 'Enable Browser Push Alerts')}
            </button>

            <button
              className="btn"
              onClick={handleSendTestNotification}
              disabled={sendingTest}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem' }}
            >
              <Send size={16} className={sendingTest ? "animate-spin" : ""} />
              {sendingTest ? 'Sending...' : 'Send Test Notification'}
            </button>
          </div>

          {pushFeedback && (
            <div style={{ marginTop: '12px', fontSize: '0.8rem', color: '#38BDF8' }}>
              ℹ️ {pushFeedback}
            </div>
          )}

          {testFeedback && (
            <div style={{
              marginTop: '12px',
              padding: '10px 14px',
              borderRadius: '6px',
              fontSize: '0.8rem',
              background: testFeedback.status === 'SUCCESS' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(56, 189, 248, 0.1)',
              border: `1px solid ${testFeedback.status === 'SUCCESS' ? 'var(--status-normal)' : '#0284C7'}`,
              color: testFeedback.status === 'SUCCESS' ? '#34D399' : '#38BDF8'
            }}>
              {testFeedback.message}
            </div>
          )}
        </div>

        {/* Channel 2: SMS & Telecom Gateway Interface */}
        <div className="card" style={{ gridColumn: 'span 6', border: '1px solid #334155' }}>
          <div className="card-header flex justify-between items-center">
            <div className="flex items-center gap-2">
              <MessageSquare size={20} className="text-muted" />
              <span className="card-title">SMS Broadcast Gateway (TRAI DLT)</span>
            </div>
            <span className="alert-badge" style={{ backgroundColor: '#1E293B', color: '#94A3B8' }}>
              {smsChannel?.status || 'NOT CONFIGURED'}
            </span>
          </div>

          <p className="text-muted" style={{ fontSize: '0.875rem', lineHeight: '1.6' }}>
            Multi-channel SMS interface architecture is defined. Requires mandatory Enterprise Entity
            Registration and Transactional Header approval on Indian Telecom DLT portals (TRAI TCCCPR 2018).
          </p>

          <div style={{ marginTop: '12px', fontSize: '0.8rem', color: '#94A3B8' }}>
            DLT Entity Status: <strong>PENDING REGISTRATION</strong> | Sender Header: <strong>SKMFLW (Reserved)</strong>
          </div>

          <div style={{ marginTop: '16px', padding: '10px 12px', background: 'var(--bg-main)', borderRadius: '6px', fontSize: '0.8rem', color: '#64748B' }}>
            ℹ️ SMS gateway remains decommissioned until official telecom credentials, DLT template approval, and explicit citizen consent registers are finalized.
          </div>
        </div>

      </div>

      {/* Active Warning Banner */}
      <div className="card" style={{
        border: `1px solid ${activeAlerts.length > 0 ? 'var(--status-warning)' : 'var(--border-color)'}`
      }}>
        <div className="card-header flex justify-between items-center">
          <div className="flex items-center gap-2">
            <ShieldAlert size={20} className={activeAlerts.length > 0 ? "text-warning" : "text-normal"} />
            <span className="card-title">Operational Warning State — Chungthang Basin</span>
          </div>

          <div>
            {activeAlerts.length > 0 ? (
              <span className="alert-badge alert-warning animate-in">
                {activeAlerts[0].severity}: {activeAlerts[0].headline}
              </span>
            ) : (
              <span className="alert-badge alert-normal flex items-center gap-1">
                <CheckCircle size={14} /> NO ACTIVE FLOOD HAZARD
              </span>
            )}
          </div>
        </div>

        <p className="text-muted" style={{ fontSize: '0.9rem', lineHeight: '1.6' }}>
          Monitors both real-time Open-Meteo precipitation accumulations and hydrological routing simulations.
          Alert thresholds are <strong>uncalibrated prototype demonstration settings</strong> until validated with CWC Chungthang gauge telemetry.
        </p>
      </div>

      {/* Live & Simulated Alert Registry Table */}
      <div className="card">
        <div className="card-header flex justify-between items-center">
          <span className="card-title">Auditable Alert Registry & Lifecycle Audit</span>
          <span className="text-muted" style={{ fontSize: '0.85rem' }}>Total Records: {alerts.length}</span>
        </div>

        {loading ? (
          <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Loading alert records from backend...
          </div>
        ) : alerts.length === 0 ? (
          <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No persistent alert records found. Run a simulation scenario or ingest rainfall data to generate alerts.
          </div>
        ) : (
          <div style={{ overflowX: 'auto', marginTop: '8px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '10px 12px' }}>Timestamp (UTC)</th>
                  <th style={{ padding: '10px 12px' }}>Mode</th>
                  <th style={{ padding: '10px 12px' }}>Severity</th>
                  <th style={{ padding: '10px 12px' }}>Zone</th>
                  <th style={{ padding: '10px 12px' }}>Headline / Rule</th>
                  <th style={{ padding: '10px 12px' }}>Peak Q / Metric</th>
                  <th style={{ padding: '10px 12px' }}>Lifecycle Status</th>
                  <th style={{ padding: '10px 12px' }}>Delivery Attempts</th>
                  <th style={{ padding: '10px 12px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a) => {
                  const isSim = a.alert_type === 'SIMULATION';
                  const isTest = a.alert_type === 'TEST';
                  const isAcked = a.status === 'ACKNOWLEDGED';

                  return (
                    <tr key={a.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>
                        {a.created_at ? new Date(a.created_at).toLocaleString() : 'N/A'}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <span style={{
                          fontSize: '0.7rem',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: isSim ? '#F59E0B' : (isTest ? '#475569' : '#0284C7'),
                          color: '#FFF',
                          fontWeight: 700
                        }}>
                          {a.alert_type}
                        </span>
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <span className={`alert-badge ${
                          a.severity === 'CRITICAL' || a.severity === 'WARNING'
                            ? 'alert-warning'
                            : (a.severity === 'WATCH' ? 'alert-watch' : 'alert-normal')
                        }`} style={{ fontSize: '0.75rem', padding: '2px 8px' }}>
                          {a.severity}
                        </span>
                      </td>
                      <td style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>
                        {a.zone || 'Chungthang Basin'}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <div style={{ fontWeight: 600 }}>{a.headline}</div>
                        <div className="text-muted" style={{ fontSize: '0.75rem', marginTop: '2px' }}>
                          {a.trigger_rule}
                        </div>
                      </td>
                      <td style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>
                        {a.predicted_discharge ? `${a.predicted_discharge} m³/s` : (
                          a.trigger_inputs?.p_3h_mm ? `3h: ${a.trigger_inputs.p_3h_mm} mm` : '--'
                        )}
                      </td>
                      <td style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>
                        <span style={{
                          fontWeight: 600,
                          fontSize: '0.75rem',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: isAcked ? 'rgba(56, 189, 248, 0.15)' : (a.status === 'ACTIVE' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)'),
                          color: isAcked ? '#38BDF8' : (a.status === 'ACTIVE' ? '#F87171' : '#34D399')
                        }}>
                          {a.status}
                        </span>
                        {isAcked && a.acknowledged_by && (
                          <div className="text-muted" style={{ fontSize: '0.7rem', marginTop: '2px' }}>
                            By: {a.acknowledged_by}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        {a.deliveries && a.deliveries.length > 0 ? (
                          <div style={{ fontSize: '0.75rem' }}>
                            {a.deliveries.map((d, idx) => {
                              const displayLabel = d.status === 'SENT' ? 'SENT TO PUSH PROVIDER' : d.status;
                              const isSuccess = d.status === 'SENT';
                              return (
                                <div
                                  key={idx}
                                  title="Accepted by WebPush gateway service. Does not guarantee physical screen display or human sight."
                                  style={{
                                    color: isSuccess ? 'var(--status-normal)' : (d.status === 'EXPIRED' ? 'var(--text-muted)' : 'var(--status-warning)')
                                  }}
                                >
                                  {d.channel}: <strong>{displayLabel}</strong> ({d.recipient})
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <span className="text-muted" style={{ fontSize: '0.75rem' }}>None</span>
                        )}
                      </td>
                      <td style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>
                        <div className="flex items-center gap-2">
                          {a.status === 'ACTIVE' && (
                            <button
                              className="btn"
                              style={{ padding: '3px 8px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                              onClick={() => setAckTargetId(a.id)}
                            >
                              <CheckSquare size={12} /> Acknowledge
                            </button>
                          )}

                          {a.has_cap_xml && (
                            <button
                              className="btn"
                              style={{ padding: '3px 8px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                              onClick={() => setSelectedCapXml(selectedCapXml?.id === a.id ? null : { id: a.id, xml: a.cap_xml || '' })}
                            >
                              <Code size={12} /> {selectedCapXml?.id === a.id ? 'Hide' : 'CAP XML'}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Selected CAP XML Inspector */}
        {selectedCapXml && (
          <div style={{ marginTop: '16px', padding: '16px', background: 'var(--bg-main)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
            <div className="flex justify-between items-center" style={{ marginBottom: '8px' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>CAP v1.2 XML Document ({selectedCapXml.id})</span>
              <button className="btn" style={{ padding: '2px 8px', fontSize: '0.75rem' }} onClick={() => setSelectedCapXml(null)}>Close</button>
            </div>
            <pre style={{ overflowX: 'auto', fontSize: '0.8rem', color: '#94A3B8', maxHeight: '250px' }}>
              {selectedCapXml.xml}
            </pre>
          </div>
        )}
      </div>

      {/* Operator Acknowledgement Modal/Drawer */}
      {ackTargetId && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 999
        }}>
          <div className="card" style={{ width: '450px', maxWidth: '90%', background: 'var(--bg-panel)', border: '1px solid var(--border-color)' }}>
            <div className="card-header flex justify-between items-center">
              <span className="card-title">Acknowledge Alert ({ackTargetId})</span>
              <button className="btn" style={{ padding: '2px 8px' }} onClick={() => setAckTargetId(null)}>✕</button>
            </div>

            <form onSubmit={handleAcknowledgeSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '12px' }}>
              <div>
                <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Operator Name / Badge ID *
                </label>
                <input
                  type="text"
                  required
                  value={operatorName}
                  onChange={(e) => setOperatorName(e.target.value)}
                  placeholder="e.g. Duty Officer Sonam Bhutia"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    background: 'var(--bg-main)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-main)',
                    fontSize: '0.875rem'
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Response Actions / Notes (Optional)
                </label>
                <textarea
                  value={ackNotes}
                  onChange={(e) => setAckNotes(e.target.value)}
                  placeholder="e.g. Evacuation advisory dispatched to Chungthang SDM office."
                  rows={3}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    background: 'var(--bg-main)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-main)',
                    fontSize: '0.875rem',
                    resize: 'vertical'
                  }}
                />
              </div>

              <div className="flex justify-end gap-3" style={{ marginTop: '8px' }}>
                <button type="button" className="btn" onClick={() => setAckTargetId(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={acking || !operatorName.trim()}>
                  {acking ? 'Recording...' : 'Confirm Acknowledgement'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Operator Authentication Modal */}
      {showKeyModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div className="card" style={{ width: '450px', maxWidth: '90%', background: 'var(--bg-panel)', border: '1px solid var(--border-color)' }}>
            <div className="card-header flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Key size={18} className="text-warning" />
                <span className="card-title">Operator Authentication Key</span>
              </div>
              <button className="btn" style={{ padding: '2px 8px' }} onClick={() => setShowKeyModal(false)}>✕</button>
            </div>

            {authError && (
              <div style={{ padding: '10px 12px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #DC2626', borderRadius: '6px', color: '#F87171', fontSize: '0.8rem', marginTop: '10px' }}>
                {authError}
              </div>
            )}

            <div style={{ marginTop: '14px', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
              Administrative actions (acknowledging alerts, dispatching test notifications) require an authorized <code>X-Admin-Key</code> whenever configured on the server.
            </div>

            <div style={{ marginTop: '12px' }}>
              <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                Admin Secret Key:
              </label>
              <input
                type="password"
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                placeholder="Enter secret key..."
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  background: 'var(--bg-main)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-main)',
                  fontSize: '0.875rem'
                }}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px', display: 'block' }}>
                Stored in session-scoped browser memory (cleared on tab close). Never logged or included in URLs.
              </span>
            </div>

            <div className="flex justify-between items-center" style={{ marginTop: '16px' }}>
              {operatorKey ? (
                <button
                  type="button"
                  className="btn"
                  style={{ color: '#F87171', fontSize: '0.8rem' }}
                  onClick={() => {
                    saveOperatorKey('');
                    setKeyInput('');
                    setShowKeyModal(false);
                  }}
                >
                  Clear Session Key
                </button>
              ) : <div />}

              <div className="flex gap-2">
                <button type="button" className="btn" onClick={() => setShowKeyModal(false)}>Cancel</button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    saveOperatorKey(keyInput);
                    setShowKeyModal(false);
                  }}
                >
                  Save Key for Session
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Simulated Scenario Alert (Preserved from existing functionality) */}
      {isSimWarning && result && (
        <div className="card" style={{ border: '1px solid var(--status-warning)' }}>
          <div className="card-header flex justify-between items-center" style={{ borderBottomColor: 'var(--status-warning)' }}>
            <span className="card-title text-warning flex items-center gap-2">
              <ShieldAlert size={18} /> Simulated Scenario Warning: Chungthang Basin, Sikkim
            </span>
            <span className="text-muted" style={{ fontSize: '0.875rem' }}>{new Date().toLocaleString()}</span>
          </div>

          <div className="dashboard-grid" style={{ padding: 0, height: 'auto', marginTop: '12px' }}>
            <div style={{ gridColumn: 'span 4' }}>
              <div className="flex" style={{ flexDirection: 'column', gap: '12px', fontSize: '0.875rem' }}>
                <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                  <span className="text-muted">Severity</span>
                  <span className="text-warning" style={{ fontWeight: 'bold' }}>Extreme</span>
                </div>
                <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                  <span className="text-muted">Mode</span>
                  <span style={{ fontWeight: 'bold', color: '#F59E0B' }}>SIMULATION (TEST ONLY)</span>
                </div>
              </div>
            </div>

            <div style={{ gridColumn: 'span 4' }}>
              <div className="flex" style={{ flexDirection: 'column', gap: '12px', fontSize: '0.875rem' }}>
                <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                  <span className="text-muted">Predicted Peak Q</span>
                  <span style={{ fontWeight: 'bold', color: 'var(--status-warning)' }}>
                    {result.metrics.predicted_discharge.toLocaleString()} m³/s
                  </span>
                </div>
                <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                  <span className="text-muted">Critical Threshold (Qcrit)</span>
                  <span style={{ fontWeight: 'bold' }}>{result.metrics.qcrit} m³/s</span>
                </div>
              </div>
            </div>

            <div style={{ gridColumn: 'span 4' }}>
              <div className="flex" style={{ flexDirection: 'column', gap: '12px', fontSize: '0.875rem' }}>
                <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                  <span className="text-muted">Water Stage</span>
                  <span style={{ fontWeight: 'bold' }}>{result.metrics.stage_m.toFixed(2)} m</span>
                </div>
                <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                  <span className="text-muted">Impact</span>
                  <span className="text-warning" style={{ fontWeight: 'bold' }}>
                    {result.metrics.flooded_cells} cells affected
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-4 flex gap-4" style={{ paddingTop: '16px', borderTop: '1px solid var(--border-color)' }}>
            <button className="btn btn-primary" onClick={() => setShowSimCap(!showSimCap)}>
              <Code size={16} /> {showSimCap ? 'Hide Simulated CAP XML' : 'View Simulated CAP v1.2 XML'}
            </button>
          </div>

          {showSimCap && (
            <div style={{ marginTop: '16px', padding: '16px', background: 'var(--bg-main)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <pre style={{ overflowX: 'auto', fontSize: '0.8rem', color: '#94A3B8' }}>
                {result.cap_xml || '<!-- CAP XML not generated -->'}
              </pre>
            </div>
          )}
        </div>
      )}

    </div>
  );
}
