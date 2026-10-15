import { useAppStore } from '../stores/appStore';
import FloodMap from '../map/FloodMap';

export default function Predictions() {
  const { result, simulationStatus, isSimulating } = useAppStore();
  const isWarning = result?.metrics?.hazard === 'FLASH FLOOD WARNING';

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="flex justify-between items-center">
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>ST-GNN Hydrological Inference</h2>
          <p className="text-muted" style={{ fontSize: '0.875rem', marginTop: '4px' }}>
            Physics-guided Spatio-Temporal Graph Neural Network for Flash Flood Early Warning
          </p>
        </div>
        <div className="flex gap-4">
          <span className="alert-badge" style={{ backgroundColor: 'var(--bg-panel)', color: 'var(--text-muted)' }}>
            Model: {result?.provenance?.model || 'ST-GNN-v1.0 (Ready)'}
          </span>
          <span className="alert-badge" style={{ backgroundColor: 'var(--bg-panel)', color: 'var(--text-muted)' }}>
            Status: {simulationStatus || 'Standby'}
          </span>
        </div>
      </div>

      <div className="dashboard-grid" style={{ height: 'auto', padding: 0 }}>
        
        {/* Core Prediction Metrics */}
        <div className="card" style={{ gridColumn: 'span 8', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
          <div className="stat-box" style={{ background: 'var(--bg-main)', border: '1px solid var(--border-color)' }}>
            <span className="stat-label">Predicted Peak (Qpred)</span>
            {isSimulating ? (
              <span className="stat-value" style={{ fontSize: '1.5rem', color: 'var(--accent-primary)' }}>COMPUTING...</span>
            ) : !result ? (
              <span className="stat-value" style={{ fontSize: '1.25rem', color: '#94A3B8' }}>READY TO INFER</span>
            ) : (
              <span className="stat-value" style={{ fontSize: '2rem', color: isWarning ? 'var(--status-warning)' : 'var(--accent-primary)' }}>
                {result.metrics.predicted_discharge.toLocaleString()} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>m³/s</span>
              </span>
            )}
          </div>
          <div className="stat-box" style={{ background: 'var(--bg-main)', border: '1px solid var(--border-color)' }}>
            <span className="stat-label">Critical Threshold (Qcrit)</span>
            <span className="stat-value" style={{ fontSize: '2rem' }}>
              {result ? `${result.metrics.qcrit} ` : '900 '}
              <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>m³/s</span>
            </span>
            <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Prototype assumption</span>
          </div>
          <div className="stat-box" style={{ background: 'var(--bg-main)', border: '1px solid var(--border-color)' }}>
            <span className="stat-label">Rate of Change (dQ/dt)</span>
            <span className="stat-value" style={{ fontSize: '2rem' }}>
              {result ? `${result.metrics.dq_dt} ` : '0.000 '}
              <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>m³/s²</span>
            </span>
          </div>
        </div>

        {/* Hazard Classification */}
        <div className="card flex items-center justify-center" style={{ gridColumn: 'span 4', flexDirection: 'column', gap: '16px' }}>
          <span className="text-muted">Hazard Classification</span>
          {isSimulating ? (
            <div className="alert-badge alert-watch" style={{ fontSize: '1.1rem', padding: '12px 24px' }}>
              CALCULATING HAZARD...
            </div>
          ) : isWarning ? (
            <div className="alert-badge alert-warning animate-in" style={{ fontSize: '1.25rem', padding: '12px 24px' }}>
              FLASH FLOOD WARNING
            </div>
          ) : result ? (
            <div className="alert-badge alert-normal" style={{ fontSize: '1.25rem', padding: '12px 24px' }}>
              {result.metrics.hazard || 'NORMAL'}
            </div>
          ) : (
            <div className="alert-badge alert-normal" style={{ fontSize: '1.1rem', padding: '12px 24px' }}>
              STANDBY (READY)
            </div>
          )}
        </div>

        {/* Inundation Extent Map */}
        <div className="card" style={{ gridColumn: 'span 12', height: '480px', display: 'flex', flexDirection: 'column' }}>
          <div className="card-header flex justify-between">
            <span className="card-title">Inundation Extent & Basin Topology (Chungthang)</span>
            <div className="flex gap-4 text-sm text-muted">
              <span>Stage: {result ? `${result.metrics.stage_m}m` : '0.00m'}</span>
              <span>Flooded Cells: {result ? result.metrics.flooded_cells : 0}</span>
            </div>
          </div>
          <div style={{ flex: 1, position: 'relative', borderRadius: '8px', overflow: 'hidden' }}>
            <FloodMap isWarning={isWarning} inundationGeoJSON={result?.inundation_geojson} />
            {!result && !isSimulating && (
              <div style={{
                position: 'absolute', top: 16, right: 16,
                background: 'rgba(15, 23, 42, 0.85)',
                padding: '8px 16px',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                fontSize: '0.85rem',
                color: 'var(--text-muted)',
                zIndex: 10
              }}>
                Terrain Basemap Ready | Trigger simulation to compute flood inundation
              </div>
            )}
          </div>
        </div>

        {/* ST-GNN Provenance Tracking */}
        <div className="card" style={{ gridColumn: 'span 12' }}>
          <div className="card-header">
            <span className="card-title">Model Architecture & Provenance Tracking</span>
          </div>
          <div className="dashboard-grid" style={{ padding: 0, height: 'auto', marginTop: '16px' }}>
            <div className="stat-box" style={{ gridColumn: 'span 3', background: 'var(--bg-main)', border: '1px solid var(--border-color)' }}>
              <span className="stat-label">Spatial Layers</span>
              <span style={{ fontWeight: 'bold' }}>2x GCN (Adjacency Matrix)</span>
              <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Learns river reach upstream topology</span>
            </div>
            <div className="stat-box" style={{ gridColumn: 'span 3', background: 'var(--bg-main)', border: '1px solid var(--border-color)' }}>
              <span className="stat-label">Temporal Dynamic</span>
              <span style={{ fontWeight: 'bold' }}>GRU (16 hidden units)</span>
              <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Processes 12 timesteps (3 hours)</span>
            </div>
            <div className="stat-box" style={{ gridColumn: 'span 3', background: 'var(--bg-main)', border: '1px solid var(--border-color)' }}>
              <span className="stat-label">Physics Constraint</span>
              <span style={{ fontWeight: 'bold' }}>Saint-Venant Skip</span>
              <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Conserves 1D mass continuity</span>
            </div>
            <div className="stat-box" style={{ gridColumn: 'span 3', background: 'var(--bg-main)', border: '1px solid var(--border-color)' }}>
              <span className="stat-label">Target Station</span>
              <span style={{ fontWeight: 'bold' }}>CWC Chungthang</span>
              <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Lat: 27.5851°N, Lon: 88.6551°E</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
