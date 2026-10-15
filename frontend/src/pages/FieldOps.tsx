import { useAppStore } from '../stores/appStore';
import { Navigation, Users, Truck, Radio, CheckCircle, AlertTriangle } from 'lucide-react';

export default function FieldOps() {
  const { result, isSimulating } = useAppStore();

  const isWarning = result?.metrics?.hazard === 'FLASH FLOOD WARNING';
  const run_id = result?.run_id || 'STANDBY-CHUNGTHANG-01';
  const hazard = result?.metrics?.hazard || 'NORMAL (STANDBY)';
  const floodedCells = result ? result.metrics.flooded_cells : 0;
  const dq_dt = result ? result.metrics.dq_dt : 0;

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="flex justify-between items-center">
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Field Operations & Emergency Coordination</h2>
          <p className="text-muted" style={{ fontSize: '0.875rem', marginTop: '4px' }}>
            Tactical response protocols and evacuation coordination for Chungthang, Sikkim
          </p>
        </div>
        <span className={`alert-badge ${isWarning ? 'alert-warning' : (isSimulating ? 'alert-watch' : 'alert-normal')}`}>
          {isSimulating ? 'ANALYZING ACTION PROTOCOLS...' : isWarning ? 'FLASH FLOOD WARNING ACTIVE' : 'ALL CLEAR (STANDBY)'}
        </span>
      </div>
      
      <div className="dashboard-grid" style={{ height: 'auto', padding: 0 }}>
        
        {/* Operational Context */}
        <div className="card" style={{ gridColumn: 'span 8' }}>
          <div className="card-header">
            <span className="card-title">Operational Context & Basin Status</span>
          </div>
          <div className="flex" style={{ flexDirection: 'column', gap: '16px' }}>
            <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="text-muted">Active Simulation / Event ID</span>
              <span style={{ fontFamily: 'monospace', fontWeight: 'bold' }}>{run_id}</span>
            </div>
            <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="text-muted">Target Basin & Station</span>
              <span style={{ fontWeight: 'bold' }}>Chungthang Basin (CWC Station, Sikkim)</span>
            </div>
            <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="text-muted">Hazard Classification</span>
              <span className={isWarning ? 'text-warning' : 'text-normal'} style={{ fontWeight: 'bold' }}>
                {hazard}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Inundation Extent</span>
              <span style={{ fontWeight: 'bold', color: isWarning ? 'var(--status-warning)' : 'inherit' }}>
                {floodedCells} cells affected
              </span>
            </div>
          </div>
        </div>

        {/* Action Recommendations */}
        <div className="card" style={{ gridColumn: 'span 4' }}>
          <div className="card-header">
            <span className="card-title">Recommended Field Actions</span>
          </div>
          <div className="flex" style={{ flexDirection: 'column', gap: '16px' }}>
            {isWarning ? (
              <>
                <div style={{ padding: '12px', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--status-warning)', borderRadius: '8px', color: 'var(--status-warning)' }}>
                  <div className="flex items-center gap-2" style={{ marginBottom: '4px' }}>
                    <AlertTriangle size={16} /> <strong>IMMEDIATE ACTION REQUIRED</strong>
                  </div>
                  Water stage predicted to breach critical bankfull threshold (dQ/dt: {dq_dt.toFixed(3)} m³/s²).
                </div>
                <ul style={{ listStyleType: 'disc', paddingLeft: '20px', color: 'var(--text-main)', fontSize: '0.875rem', lineHeight: '1.6' }}>
                  <li>Broadcast CAP v1.2 warning to NDMA and district administration.</li>
                  <li>Evacuate low-lying riverside corridors in Chungthang downstream.</li>
                  <li>Mobilize SDRF rescue teams to designated higher ground staging areas.</li>
                </ul>
              </>
            ) : (
              <>
                <div style={{ padding: '12px', backgroundColor: 'rgba(16, 185, 129, 0.1)', border: '1px solid var(--status-normal)', borderRadius: '8px', color: 'var(--status-normal)' }}>
                  <div className="flex items-center gap-2" style={{ marginBottom: '4px' }}>
                    <CheckCircle size={16} /> <strong>NORMAL MONITORING STATUS</strong>
                  </div>
                  River discharge remains within channel bankfull capacity.
                </div>
                <ul style={{ listStyleType: 'disc', paddingLeft: '20px', color: 'var(--text-muted)', fontSize: '0.875rem', lineHeight: '1.6' }}>
                  <li>Maintain automated sensor polling and watch protocols.</li>
                  <li>Verify communication links with Mangan district emergency center.</li>
                </ul>
              </>
            )}
          </div>
        </div>

        {/* Future Integrations */}
        <div className="card" style={{ gridColumn: 'span 12' }}>
          <div className="card-header">
            <span className="card-title text-muted">Emergency Infrastructure & Logistics (Field Telemetry Modules)</span>
          </div>
          <div className="dashboard-grid" style={{ padding: 0, height: 'auto', marginTop: '16px' }}>
            <div className="stat-box" style={{ gridColumn: 'span 3', opacity: 0.85, background: 'var(--bg-main)' }}>
              <Users size={24} style={{ marginBottom: '8px', color: '#38BDF8' }} />
              <span className="stat-label">Designated Relief Shelters</span>
              <span className="stat-value" style={{ fontSize: '1rem' }}>Chungthang Secondary School</span>
              <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Capacity: 450 persons (High ground)</span>
            </div>
            <div className="stat-box" style={{ gridColumn: 'span 3', opacity: 0.85, background: 'var(--bg-main)' }}>
              <Navigation size={24} style={{ marginBottom: '8px', color: '#38BDF8' }} />
              <span className="stat-label">Primary Evacuation Axis</span>
              <span className="stat-value" style={{ fontSize: '1rem' }}>NH-310A (Mangan - Chungthang)</span>
              <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Status: Operational</span>
            </div>
            <div className="stat-box" style={{ gridColumn: 'span 3', opacity: 0.85, background: 'var(--bg-main)' }}>
              <Truck size={24} style={{ marginBottom: '8px', color: '#38BDF8' }} />
              <span className="stat-label">SDRF Emergency Unit</span>
              <span className="stat-value" style={{ fontSize: '1rem' }}>Mangan Sub-division Team</span>
              <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Alert readiness: 15 min standby</span>
            </div>
            <div className="stat-box" style={{ gridColumn: 'span 3', opacity: 0.85, background: 'var(--bg-main)' }}>
              <Radio size={24} style={{ marginBottom: '8px', color: '#38BDF8' }} />
              <span className="stat-label">Emergency Broadcast</span>
              <span className="stat-value" style={{ fontSize: '1rem' }}>CAP v1.2 Gateway</span>
              <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Ready for automated dissemination</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
