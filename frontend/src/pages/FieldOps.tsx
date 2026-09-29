import { useAppStore } from '../stores/appStore';
import { Navigation, Users, Truck, Radio } from 'lucide-react';

export default function FieldOps() {
  const { result, isSimulating } = useAppStore();

  if (!result && !isSimulating) {
    return (
      <div style={{ padding: '24px', color: 'var(--text-muted)' }}>
        <p>Run a simulation to view Field Operations data.</p>
      </div>
    );
  }

  if (isSimulating) {
    return (
      <div style={{ padding: '24px', color: 'var(--text-muted)' }}>
        <p>Gathering operational context...</p>
      </div>
    );
  }

  const { metrics, run_id } = result!;
  const isWarning = metrics.hazard === 'FLASH FLOOD WARNING';

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Field Operations</h2>
      
      <div className="dashboard-grid" style={{ height: 'auto', padding: 0 }}>
        
        {/* Operational Context */}
        <div className="card" style={{ gridColumn: 'span 8' }}>
          <div className="card-header">
            <span className="card-title">Operational Context</span>
          </div>
          <div className="flex" style={{ flexDirection: 'column', gap: '16px' }}>
            <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="text-muted">Current Simulation Run</span>
              <span style={{ fontFamily: 'monospace' }}>{run_id}</span>
            </div>
            <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="text-muted">Target Basin</span>
              <span style={{ fontWeight: 'bold' }}>NER Demonstration Basin (Synthetic)</span>
            </div>
            <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="text-muted">Hazard Level</span>
              <span className={isWarning ? 'text-warning' : 'text-normal'} style={{ fontWeight: 'bold' }}>{metrics.hazard}</span>
            </div>
            <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="text-muted">Inundation Extent</span>
              <span style={{ fontWeight: 'bold' }}>{metrics.flooded_cells} cells affected</span>
            </div>
          </div>
        </div>

        {/* Action Recommendations */}
        <div className="card" style={{ gridColumn: 'span 4' }}>
          <div className="card-header">
            <span className="card-title">Recommended Actions</span>
          </div>
          <div className="flex" style={{ flexDirection: 'column', gap: '16px' }}>
            {isWarning ? (
              <>
                <div style={{ padding: '12px', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--status-warning)', borderRadius: '8px', color: 'var(--status-warning)' }}>
                  <strong>IMMEDIATE ACTION REQUIRED:</strong> Water stage predicted to exceed critical limits by {metrics.dq_dt.toFixed(2)} m³/s² rate of rise.
                </div>
                <ul style={{ listStyleType: 'disc', paddingLeft: '20px', color: 'var(--text-main)', fontSize: '0.875rem' }}>
                  <li>Generate and broadcast CAP Alert to mobile networks.</li>
                  <li>Evacuate low-lying cells adjacent to NER-042.</li>
                </ul>
              </>
            ) : (
              <div style={{ padding: '12px', backgroundColor: 'rgba(16, 185, 129, 0.1)', border: '1px solid var(--status-normal)', borderRadius: '8px', color: 'var(--status-normal)' }}>
                <strong>STANDBY:</strong> Discharge remains safely within channel capacity.
              </div>
            )}
          </div>
        </div>

        {/* Unavailable Integrations */}
        <div className="card" style={{ gridColumn: 'span 12' }}>
          <div className="card-header">
            <span className="card-title text-muted">Future Integrations (Not available in prototype)</span>
          </div>
          <div className="dashboard-grid" style={{ padding: 0, height: 'auto', marginTop: '16px' }}>
            <div className="stat-box" style={{ gridColumn: 'span 3', opacity: 0.5 }}>
              <Users size={24} style={{ marginBottom: '8px' }} />
              <span className="stat-label">Evacuation Centers</span>
              <span className="stat-value" style={{ fontSize: '1rem' }}>Pending API</span>
            </div>
            <div className="stat-box" style={{ gridColumn: 'span 3', opacity: 0.5 }}>
              <Navigation size={24} style={{ marginBottom: '8px' }} />
              <span className="stat-label">Evacuation Routes</span>
              <span className="stat-value" style={{ fontSize: '1rem' }}>Pending Integration</span>
            </div>
            <div className="stat-box" style={{ gridColumn: 'span 3', opacity: 0.5 }}>
              <Truck size={24} style={{ marginBottom: '8px' }} />
              <span className="stat-label">Response Units</span>
              <span className="stat-value" style={{ fontSize: '1rem' }}>No telemetry data</span>
            </div>
            <div className="stat-box" style={{ gridColumn: 'span 3', opacity: 0.5 }}>
              <Radio size={24} style={{ marginBottom: '8px' }} />
              <span className="stat-label">Local Broadcasters</span>
              <span className="stat-value" style={{ fontSize: '1rem' }}>CAP Integration required</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
