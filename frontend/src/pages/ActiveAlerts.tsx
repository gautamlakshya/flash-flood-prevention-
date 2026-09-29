import { useState } from 'react';
import { useAppStore } from '../stores/appStore';
import { ShieldAlert, Download, Code } from 'lucide-react';

export default function ActiveAlerts() {
  const { result, isSimulating } = useAppStore();
  const [showCap, setShowCap] = useState(false);

  if (!result && !isSimulating) {
    return (
      <div style={{ padding: '24px', color: 'var(--text-muted)' }}>
        <p>Run a simulation to view Alerts.</p>
      </div>
    );
  }

  if (isSimulating) {
    return (
      <div style={{ padding: '24px', color: 'var(--text-muted)' }}>
        <p>Analyzing risk levels...</p>
      </div>
    );
  }

  const { metrics, cap_xml } = result!;
  const isWarning = metrics.hazard === 'FLASH FLOOD WARNING';

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="flex items-center gap-4">
        <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Active Alerts</h2>
        {isWarning ? (
          <span className="alert-badge alert-warning animate-in flex items-center gap-2">
            <ShieldAlert size={16} /> FLASH FLOOD WARNING
          </span>
        ) : (
          <span className="alert-badge alert-normal">NO ACTIVE WARNINGS</span>
        )}
      </div>
      
      {isWarning && (
        <div className="dashboard-grid" style={{ height: 'auto', padding: 0 }}>
          <div className="card" style={{ gridColumn: 'span 12', border: '1px solid var(--status-warning)' }}>
            <div className="card-header" style={{ borderBottomColor: 'var(--status-warning)' }}>
              <span className="card-title text-warning">Alert Details: NER Basin</span>
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
                    <span style={{ fontWeight: 'bold' }}>NER Demonstration Basin</span>
                  </div>
                </div>
              </div>

              <div style={{ gridColumn: 'span 4' }}>
                <div className="flex" style={{ flexDirection: 'column', gap: '12px', fontSize: '0.875rem' }}>
                  <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                    <span className="text-muted">Predicted Discharge</span>
                    <span style={{ fontWeight: 'bold' }}>{metrics.predicted_discharge.toLocaleString()} m³/s</span>
                  </div>
                  <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                    <span className="text-muted">Critical Capacity (Qcrit)</span>
                    <span style={{ fontWeight: 'bold' }}>{metrics.qcrit.toLocaleString()} m³/s</span>
                  </div>
                  <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                    <span className="text-muted">Rate of Rise (dQ/dt)</span>
                    <span style={{ fontWeight: 'bold' }}>{metrics.dq_dt.toFixed(2)} m³/s²</span>
                  </div>
                </div>
              </div>

              <div style={{ gridColumn: 'span 4' }}>
                <div className="flex" style={{ flexDirection: 'column', gap: '12px', fontSize: '0.875rem' }}>
                  <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                    <span className="text-muted">Water Stage</span>
                    <span style={{ fontWeight: 'bold' }}>{metrics.stage_m.toFixed(2)} m</span>
                  </div>
                  <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                    <span className="text-muted">Inundation Status</span>
                    <span className="text-warning" style={{ fontWeight: 'bold' }}>{metrics.flooded_cells} cells flooded</span>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="mt-4 flex gap-4" style={{ paddingTop: '16px', borderTop: '1px solid var(--border-color)' }}>
              <button className="btn btn-primary" onClick={() => setShowCap(!showCap)}>
                <Code size={16} /> {showCap ? 'Hide CAP XML' : 'View CAP Alert (v1.2)'}
              </button>
              {showCap && cap_xml && (
                <button className="btn" onClick={() => {
                  const blob = new Blob([cap_xml], { type: 'text/xml' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `CAP_Alert_${result!.run_id}.xml`;
                  a.click();
                }}>
                  <Download size={16} /> Export XML
                </button>
              )}
            </div>
            
            {showCap && cap_xml && (
              <div className="mt-4" style={{ background: '#0f172a', padding: '16px', borderRadius: '8px', overflowX: 'auto' }}>
                <pre style={{ margin: 0, fontSize: '0.875rem', color: '#38bdf8' }}>
                  <code>{cap_xml}</code>
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
      
      {!isWarning && !isSimulating && (
        <div className="card" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
          <ShieldAlert size={48} style={{ opacity: 0.5, margin: '0 auto 16px' }} />
          <p>No active flood warnings for the current scenario.</p>
          <p style={{ fontSize: '0.875rem', marginTop: '8px' }}>Qpred ({metrics.predicted_discharge.toLocaleString()} m³/s) is safely below Qcrit ({metrics.qcrit.toLocaleString()} m³/s).</p>
        </div>
      )}
    </div>
  );
}
