import { useAppStore } from '../stores/appStore';

export default function Hydrology() {
  const { result, isSimulating } = useAppStore();

  if (!result && !isSimulating) {
    return (
      <div style={{ padding: '24px', color: 'var(--text-muted)' }}>
        <p>Run a simulation to view Hydrology data.</p>
      </div>
    );
  }

  if (isSimulating) {
    return (
      <div style={{ padding: '24px', color: 'var(--text-muted)' }}>
        <p>Loading hydrology models...</p>
      </div>
    );
  }

  const { metrics, timeseries } = result!;

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Hydrology Module (SCS-CN)</h2>
      
      <div className="dashboard-grid" style={{ height: 'auto', padding: 0 }}>
        
        {/* Core parameters */}
        <div className="card" style={{ gridColumn: 'span 4' }}>
          <div className="card-header">
            <span className="card-title">Catchment Parameters</span>
          </div>
          <div className="flex" style={{ flexDirection: 'column', gap: '16px' }}>
            <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="text-muted">AMC Condition</span>
              <span style={{ fontWeight: 'bold' }}>{metrics.amc}</span>
            </div>
            <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="text-muted">Adjusted Curve Number (CN)</span>
              <span style={{ fontWeight: 'bold' }}>{metrics.cn.toFixed(2)}</span>
            </div>
            <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="text-muted">Retention Capacity (S)</span>
              <span style={{ fontWeight: 'bold' }}>{metrics.s_mm.toFixed(2)} mm</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Peak Runoff Volume</span>
              <span style={{ fontWeight: 'bold' }}>{metrics.peak_runoff_volume.toLocaleString()} m³</span>
            </div>
          </div>
        </div>

        {/* Data flow explanation */}
        <div className="card" style={{ gridColumn: 'span 8' }}>
          <div className="card-header">
            <span className="card-title">Data Flow & Formulas</span>
          </div>
          <div className="flex" style={{ gap: '24px', alignItems: 'center', justifyContent: 'space-between', padding: '16px 0' }}>
            <div className="stat-box" style={{ alignItems: 'center' }}>
              <span className="stat-label">RAINFALL</span>
              <span style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{timeseries.reduce((a, b) => a + b.rainfall_mm, 0).toFixed(1)} mm</span>
            </div>
            <div style={{ color: 'var(--accent-blue)' }}>→</div>
            <div className="stat-box" style={{ alignItems: 'center' }}>
              <span className="stat-label">AMC + SLOPE</span>
              <span style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>CN: {metrics.cn.toFixed(1)}</span>
            </div>
            <div style={{ color: 'var(--accent-blue)' }}>→</div>
            <div className="stat-box" style={{ alignItems: 'center' }}>
              <span className="stat-label">RETENTION (S)</span>
              <span style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{metrics.s_mm.toFixed(1)} mm</span>
            </div>
            <div style={{ color: 'var(--accent-blue)' }}>→</div>
            <div className="stat-box" style={{ alignItems: 'center' }}>
              <span className="stat-label">SURFACE RUNOFF</span>
              <span style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{metrics.peak_runoff_volume.toLocaleString()} m³</span>
            </div>
          </div>
          <div style={{ marginTop: '24px', padding: '16px', background: 'var(--bg-main)', borderRadius: '8px', border: '1px solid var(--border-color)', fontSize: '0.875rem' }}>
            <p style={{ marginBottom: '8px' }}><strong>SCS-CN Formulas Used:</strong></p>
            <ul style={{ listStyleType: 'disc', paddingLeft: '20px', color: 'var(--text-muted)' }}>
              <li>S = (25400 / CN) - 254</li>
              <li>Initial Abstraction (Ia) = 0.2 * S</li>
              <li>Runoff Depth (Q) = (P - Ia)² / (P - Ia + S) for P &gt; Ia</li>
              <li>Runoff Volume = Q * Catchment Area (50 km²)</li>
            </ul>
          </div>
        </div>

      </div>
    </div>
  );
}
