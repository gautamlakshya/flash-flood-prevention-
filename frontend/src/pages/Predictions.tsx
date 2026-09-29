import { useAppStore } from '../stores/appStore';
import FloodMap from '../map/FloodMap';

export default function Predictions() {
  const { result, simulationStatus, isSimulating } = useAppStore();
  const isWarning = result?.metrics?.hazard === 'FLASH FLOOD WARNING';

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="flex justify-between items-center">
        <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>ST-GNN Hydrological Inference</h2>
        <div className="flex gap-4">
          <span className="alert-badge" style={{ backgroundColor: 'var(--bg-panel)', color: 'var(--text-muted)' }}>
            Model: {result?.model_version || 'ST-GNN-v1.0 (Waiting)'}
          </span>
          <span className="alert-badge" style={{ backgroundColor: 'var(--bg-panel)', color: 'var(--text-muted)' }}>
            Status: {simulationStatus}
          </span>
        </div>
      </div>

      <div className="dashboard-grid" style={{ height: 'auto', padding: 0 }}>
        
        {/* Core Prediction Metrics */}
        <div className="card" style={{ gridColumn: 'span 8', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
          <div className="stat-box" style={{ background: 'var(--bg-main)', border: '1px solid var(--border-color)' }}>
            <span className="stat-label">Predicted Peak (Qpred)</span>
            {result?.metrics?.predicted_discharge === 'NOT_CONFIGURED' || !result ? (
              <span className="stat-value" style={{ fontSize: '1.5rem', color: '#94A3B8' }}>NOT CONFIGURED</span>
            ) : (
              <span className="stat-value" style={{ fontSize: '2rem', color: 'var(--accent-primary)' }}>
                {result.metrics.predicted_discharge.toLocaleString()} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>m³/s</span>
              </span>
            )}
          </div>
          <div className="stat-box" style={{ background: 'var(--bg-main)', border: '1px solid var(--border-color)' }}>
            <span className="stat-label">Critical Threshold (Qcrit)</span>
            <span className="stat-value" style={{ fontSize: '2rem' }}>
              {result && result.metrics.qcrit !== 'NOT_CONFIGURED' ? `${result.metrics.qcrit} ` : 'NOT CONFIGURED '}
              {result && result.metrics.qcrit !== 'NOT_CONFIGURED' && <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>m³/s</span>}
            </span>
          </div>
          <div className="stat-box" style={{ background: 'var(--bg-main)', border: '1px solid var(--border-color)' }}>
            <span className="stat-label">Rate of Change (dQ/dt)</span>
            <span className="stat-value" style={{ fontSize: '2rem' }}>
              {result && result.metrics.dq_dt !== 'NOT_CONFIGURED' ? `${result.metrics.dq_dt} ` : 'NOT CONFIGURED '}
              {result && result.metrics.dq_dt !== 'NOT_CONFIGURED' && <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>m³/s²</span>}
            </span>
          </div>
        </div>

        {/* Hazard Classification */}
        <div className="card flex items-center justify-center" style={{ gridColumn: 'span 4', flexDirection: 'column', gap: '16px' }}>
          <span className="text-muted">Hazard Classification</span>
          {result?.metrics?.hazard === 'NOT_CONFIGURED' ? (
            <div className="alert-badge" style={{ backgroundColor: '#475569', fontSize: '1.25rem', padding: '12px 24px' }}>
              WAITING FOR DATA
            </div>
          ) : isWarning ? (
             <div className="alert-badge alert-warning" style={{ fontSize: '1.25rem', padding: '12px 24px' }}>
               FLASH FLOOD WARNING
             </div>
          ) : result ? (
             <div className="alert-badge alert-normal" style={{ fontSize: '1.25rem', padding: '12px 24px' }}>
               {result.metrics.hazard}
             </div>
          ) : (
            <div className="text-muted">Run simulation</div>
          )}
        </div>

        {/* Inundation Extent Map */}
        <div className="card" style={{ gridColumn: 'span 12', height: '500px', display: 'flex', flexDirection: 'column' }}>
          <div className="card-header flex justify-between">
            <span className="card-title">Inundation Extent Map (CartoDEM)</span>
            <div className="flex gap-4 text-sm text-muted">
              <span>Stage: {result && result.metrics.stage_m !== 'NOT_CONFIGURED' ? `${result.metrics.stage_m}m` : 'NOT_CONFIGURED'}</span>
              <span>Flooded Cells: {result ? result.metrics.flooded_cells : '---'}</span>
            </div>
          </div>
          <div style={{ flex: 1, position: 'relative', borderRadius: '8px', overflow: 'hidden' }}>
             <FloodMap isWarning={isWarning} inundationGeoJSON={result?.inundation_geojson} />
             {(!result || result.metrics.stage_m === 'NOT_CONFIGURED') && (
               <div style={{
                 position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                 background: 'rgba(15, 23, 42, 0.8)',
                 display: 'flex', alignItems: 'center', justifyContent: 'center',
                 zIndex: 1000
               }}>
                 <span className="text-muted" style={{ fontSize: '1.25rem' }}>
                   {isSimulating ? 'Processing Terrain Data...' : 'Inundation Map Not Configured (Missing Real DEM)'}
                 </span>
               </div>
             )}
          </div>
        </div>

        {/* ST-GNN Provenance Tracking */}
        <div className="card" style={{ gridColumn: 'span 12' }}>
           <div className="card-header">
             <span className="card-title">Inference Provenance (Data Lineage)</span>
           </div>
           <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginTop: '16px' }}>
             <div className="stat-box" style={{ background: 'var(--bg-main)' }}>
               <span className="stat-label">Model Checkpoint</span>
               <span style={{ fontSize: '0.875rem', marginTop: '4px', fontFamily: 'monospace' }}>
                 {result?.provenance?.model || 'WAITING'}
               </span>
             </div>
             <div className="stat-box" style={{ background: 'var(--bg-main)' }}>
               <span className="stat-label">Rainfall Source</span>
               <span style={{ fontSize: '0.875rem', marginTop: '4px' }}>
                 {result?.provenance?.rainfall || 'WAITING'}
               </span>
             </div>
             <div className="stat-box" style={{ background: 'var(--bg-main)' }}>
               <span className="stat-label">Hydrology Targets</span>
               <span style={{ fontSize: '0.875rem', marginTop: '4px' }}>
                 {result?.provenance?.hydrology || 'WAITING'}
               </span>
             </div>
             <div className="stat-box" style={{ background: 'var(--bg-main)' }}>
               <span className="stat-label">DEM Base</span>
               <span style={{ fontSize: '0.875rem', marginTop: '4px' }}>
                 {result?.provenance?.dem || 'WAITING'}
               </span>
             </div>
           </div>
        </div>

      </div>
    </div>
  );
}
