import { useState } from 'react';
import { useAppStore } from '../stores/appStore';
import { ShieldAlert, Code, CheckCircle, Info } from 'lucide-react';

export default function ActiveAlerts() {
  const { result, isSimulating } = useAppStore();
  const [showCap, setShowCap] = useState(false);

  const isWarning = result?.metrics?.hazard === 'FLASH FLOOD WARNING';

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Active Alerts & Warning System</h2>
          {isSimulating ? (
            <span className="alert-badge alert-watch animate-in">EVALUATING RISK...</span>
          ) : isWarning ? (
            <span className="alert-badge alert-warning animate-in flex items-center gap-2">
              <ShieldAlert size={16} /> FLASH FLOOD WARNING (SIMULATED)
            </span>
          ) : (
            <span className="alert-badge alert-normal flex items-center gap-2">
              <CheckCircle size={16} /> NO ACTIVE WARNINGS
            </span>
          )}
        </div>
      </div>
      
      {isWarning && result && (
        <div className="dashboard-grid" style={{ height: 'auto', padding: 0 }}>
          <div className="card" style={{ gridColumn: 'span 12', border: '1px solid var(--status-warning)' }}>
            <div className="card-header flex justify-between items-center" style={{ borderBottomColor: 'var(--status-warning)' }}>
              <span className="card-title text-warning flex items-center gap-2">
                <ShieldAlert size={18} /> Simulated Warning: Chungthang Basin, Sikkim
              </span>
              <span className="text-muted" style={{ fontSize: '0.875rem' }}>{new Date().toLocaleString()}</span>
            </div>
            
            <div className="dashboard-grid" style={{ padding: 0, height: 'auto' }}>
              <div style={{ gridColumn: 'span 4' }}>
                <div className="flex" style={{ flexDirection: 'column', gap: '12px', fontSize: '0.875rem' }}>
                  <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                    <span className="text-muted">Severity</span>
                    <span className="text-warning" style={{ fontWeight: 'bold' }}>Extreme</span>
                  </div>
                  <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                    <span className="text-muted">Urgency</span>
                    <span className="text-warning" style={{ fontWeight: 'bold' }}>Immediate</span>
                  </div>
                  <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                    <span className="text-muted">Location</span>
                    <span style={{ fontWeight: 'bold' }}>Chungthang Basin (Teesta River)</span>
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
                  <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                    <span className="text-muted">Rate of Rise (dQ/dt)</span>
                    <span style={{ fontWeight: 'bold' }}>{result.metrics.dq_dt} m³/s²</span>
                  </div>
                </div>
              </div>

              <div style={{ gridColumn: 'span 4' }}>
                <div className="flex" style={{ flexDirection: 'column', gap: '12px', fontSize: '0.875rem' }}>
                  <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                    <span className="text-muted">Predicted Water Stage</span>
                    <span style={{ fontWeight: 'bold' }}>{result.metrics.stage_m.toFixed(2)} m</span>
                  </div>
                  <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                    <span className="text-muted">Inundation Impact</span>
                    <span className="text-warning" style={{ fontWeight: 'bold' }}>
                      {result.metrics.flooded_cells} cells affected ({result.metrics.inundation_polygons} polygons)
                    </span>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="mt-4 flex gap-4" style={{ paddingTop: '16px', borderTop: '1px solid var(--border-color)' }}>
              <button className="btn btn-primary" onClick={() => setShowCap(!showCap)}>
                <Code size={16} /> {showCap ? 'Hide CAP XML' : 'View CAP v1.2 XML Document'}
              </button>
            </div>

            {showCap && (
              <div style={{ marginTop: '16px', padding: '16px', background: 'var(--bg-main)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <pre style={{ overflowX: 'auto', fontSize: '0.8rem', color: '#94A3B8' }}>
                  {result.cap_xml || '<!-- CAP XML not generated for this event -->'}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}

      {!isWarning && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="card-header flex items-center gap-2">
            <Info size={18} className="text-normal" />
            <span className="card-title">Alert Threshold & Protocol Status</span>
          </div>
          <p className="text-muted" style={{ fontSize: '0.9rem', lineHeight: '1.6' }}>
            All hydrological monitoring points in the <strong>Chungthang Basin</strong> are currently within safe operational limits.
            Automated alerts are triggered using Common Alerting Protocol (CAP v1.2) standards when predicted discharge exceeds the bankfull capacity threshold (<strong>Qcrit = 900 m³/s, prototype assumption</strong>).
          </p>
          <div className="dashboard-grid" style={{ padding: 0, height: 'auto', marginTop: '8px' }}>
            <div className="stat-box" style={{ gridColumn: 'span 4', background: 'var(--bg-main)' }}>
              <span className="stat-label">Critical Warning Threshold</span>
              <span className="stat-value" style={{ fontSize: '1.5rem' }}>900 m³/s</span>
              <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Bankfull capacity (uncalibrated prototype assumption)</span>
            </div>
            <div className="stat-box" style={{ gridColumn: 'span 4', background: 'var(--bg-main)' }}>
              <span className="stat-label">Alert Dissemination Protocol</span>
              <span className="stat-value" style={{ fontSize: '1.5rem' }}>CAP v1.2</span>
              <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>WMO & NDMA compliant XML standard</span>
            </div>
            <div className="stat-box" style={{ gridColumn: 'span 4', background: 'var(--bg-main)' }}>
              <span className="stat-label">Demonstration Trigger</span>
              <span className="stat-value" style={{ fontSize: '1.25rem', color: '#38BDF8' }}>Extreme Cloudburst</span>
              <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Select from header and click Start Simulation</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
