import { useAppStore } from '../stores/appStore';

export default function Hydrology() {
  const { result, isSimulating } = useAppStore();

  const amc = result ? result.metrics.amc : 'AMC-II (Normal Baseline)';
  const cn = result ? result.metrics.cn.toFixed(1) : '75.0';
  const s_mm = result ? result.metrics.s_mm.toFixed(1) : '84.7';
  const peakRunoff = result ? `${result.metrics.peak_runoff_volume.toLocaleString()} m³` : 'Pending simulation';
  const totalRainfall = result && result.timeseries && result.timeseries.length > 0
    ? `${result.timeseries.reduce((a, b) => a + b.rainfall_mm, 0).toFixed(1)} mm`
    : '0.0 mm';

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="flex justify-between items-center">
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Hydrology Module (Slope-Adjusted SCS-CN)</h2>
          <p className="text-muted" style={{ fontSize: '0.875rem', marginTop: '4px' }}>
            Antecedent Moisture Condition & Runoff Volume Modeling for Chungthang Basin
          </p>
        </div>
        {!result && (
          <span className="alert-badge alert-normal">
            {isSimulating ? 'SIMULATING RUNOFF...' : 'BASELINE PARAMETERS (PROTOTYPE)'}
          </span>
        )}
        {result && (
          <span className="alert-badge alert-watch">
            SIMULATED RUNOFF (SCENARIO)
          </span>
        )}
      </div>

      {!result && !isSimulating && (
        <div style={{ background: 'var(--bg-panel)', padding: '12px 16px', borderRadius: '8px', border: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
          💡 <strong>Simulation Mode:</strong> Displaying baseline hydrological prototype assumptions (AMC-II, CN=75.0, uncalibrated). Click <strong>Start Simulation</strong> in the header to run dynamic SCS-CN rainfall-to-runoff routing.
        </div>
      )}

      <div className="dashboard-grid" style={{ height: 'auto', padding: 0 }}>

        {/* Core parameters */}
        <div className="card" style={{ gridColumn: 'span 4' }}>
          <div className="card-header">
            <span className="card-title">Catchment Parameters (Chungthang - Prototype Assumptions)</span>
          </div>
          <div className="flex" style={{ flexDirection: 'column', gap: '16px' }}>
            <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="text-muted">Soil Moisture (AMC Condition)</span>
              <span style={{ fontWeight: 'bold' }}>{amc}</span>
            </div>
            <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="text-muted">Adjusted Curve Number (CN)</span>
              <span style={{ fontWeight: 'bold' }}>{cn}</span>
            </div>
            <div className="flex justify-between border-b pb-2" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="text-muted">Potential Max Retention (S)</span>
              <span style={{ fontWeight: 'bold' }}>{s_mm} mm</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Peak Surface Runoff Volume</span>
              <span style={{ fontWeight: 'bold', color: result ? 'var(--accent-primary)' : 'inherit' }}>{peakRunoff}</span>
            </div>
          </div>
        </div>

        {/* Data flow explanation */}
        <div className="card" style={{ gridColumn: 'span 8' }}>
          <div className="card-header">
            <span className="card-title">Hydrological Transformation Flow</span>
          </div>
          <div className="flex" style={{ gap: '24px', alignItems: 'center', justifyContent: 'space-between', padding: '16px 0', flexWrap: 'wrap' }}>
            <div className="stat-box" style={{ alignItems: 'center', minWidth: '110px' }}>
              <span className="stat-label">RAINFALL (P)</span>
              <span style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>{totalRainfall}</span>
            </div>
            <div style={{ color: 'var(--accent-blue)', fontWeight: 'bold' }}>→</div>
            <div className="stat-box" style={{ alignItems: 'center', minWidth: '110px' }}>
              <span className="stat-label">SLOPE ADJUSTED</span>
              <span style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>CN: {cn}</span>
            </div>
            <div style={{ color: 'var(--accent-blue)', fontWeight: 'bold' }}>→</div>
            <div className="stat-box" style={{ alignItems: 'center', minWidth: '110px' }}>
              <span className="stat-label">RETENTION (S)</span>
              <span style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>{s_mm} mm</span>
            </div>
            <div style={{ color: 'var(--accent-blue)', fontWeight: 'bold' }}>→</div>
            <div className="stat-box" style={{ alignItems: 'center', minWidth: '110px' }}>
              <span className="stat-label">PEAK RUNOFF</span>
              <span style={{ fontSize: '1.25rem', fontWeight: 'bold', color: result ? 'var(--status-warning)' : 'inherit' }}>
                {peakRunoff}
              </span>
            </div>
          </div>
          <div style={{ marginTop: '24px', padding: '16px', background: 'var(--bg-main)', borderRadius: '8px', border: '1px solid var(--border-color)', fontSize: '0.875rem' }}>
            <p style={{ marginBottom: '8px' }}><strong>Slope-Adjusted SCS-CN Formulation:</strong></p>
            <ul style={{ listStyleType: 'disc', paddingLeft: '20px', color: 'var(--text-muted)', lineHeight: '1.6' }}>
              <li><strong>Retention Capacity:</strong> <code>S = (25400 / CN) - 254</code></li>
              <li><strong>Initial Abstraction:</strong> <code>Ia = 0.2 × S</code></li>
              <li><strong>Runoff Depth (Q):</strong> <code>Q = (P - Ia)² / (P - Ia + S)</code> for <code>P &gt; Ia</code></li>
              <li><strong>Runoff Volume:</strong> <code>Q_vol = Q × Catchment Area (Chungthang Basin)</code></li>
            </ul>
          </div>
        </div>

      </div>
    </div>
  );
}
