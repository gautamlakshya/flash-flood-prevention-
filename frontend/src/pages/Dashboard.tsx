import { useAppStore } from '../stores/appStore';
import FloodMap from '../map/FloodMap';
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

export default function Dashboard() {
  const { result, simulationStatus, isSimulating, dataMode } = useAppStore();
  const isWarning = result?.metrics?.hazard === 'FLASH FLOOD WARNING';

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

  return (
    <div className="dashboard-grid">
      {/* Map Layer */}
      <div className="map-container">
        <div style={{ position: 'absolute', top: '16px', left: '16px', zIndex: 10, background: 'var(--bg-panel)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <h3 className="card-title" style={{ marginBottom: '8px', border: 'none', padding: 0 }}>Map Layers</h3>
          <div className="flex" style={{ flexDirection: 'column', gap: '8px', fontSize: '0.875rem' }}>
            <label className="flex items-center gap-2"><input type="checkbox" defaultChecked readOnly /> Flood Inundation (CartoDEM)</label>
            <label className="flex items-center gap-2"><input type="checkbox" defaultChecked readOnly /> River Network (Teesta Basin)</label>
            <label className="flex items-center gap-2"><input type="checkbox" defaultChecked readOnly /> CWC Chungthang Outlet Station</label>
          </div>
        </div>
        <FloodMap isWarning={isWarning} inundationGeoJSON={result?.inundation_geojson} />
      </div>

      {/* Side Panels */}
      <div className="card" style={{ gridColumn: 'span 4', gridRow: 'span 5' }}>
        <div className="card-header">
          <span className="card-title">Event Status</span>
          {result?.metrics?.hazard === 'NOT_CONFIGURED' ? (
            <span className="alert-badge" style={{ backgroundColor: '#475569' }}>WAITING FOR REAL DATA</span>
          ) : isWarning ? (
            <span className="alert-badge alert-warning animate-in">FLASH FLOOD WARNING</span>
          ) : result ? (
            <span className="alert-badge alert-normal">{result.metrics.hazard || 'NORMAL'}</span>
          ) : (
            <span className="alert-badge alert-normal">SYSTEM READY (IDLE)</span>
          )}
        </div>
        <div className="flex" style={{ flexDirection: 'column', gap: '16px' }}>
          <div className="stat-box">
            <span className="stat-label">Predicted Peak Discharge (Chungthang Outlet)</span>
            {isSimulating ? (
              <span className="stat-value" style={{ fontSize: '1.25rem', color: 'var(--accent-primary)' }}>COMPUTING...</span>
            ) : !result ? (
              <span className="stat-value" style={{ fontSize: '1.25rem', color: '#94A3B8' }}>READY TO SIMULATE</span>
            ) : result.metrics.predicted_discharge === 'NOT_CONFIGURED' ? (
              <span className="stat-value" style={{ fontSize: '1rem', color: '#94A3B8' }}>NOT CONFIGURED</span>
            ) : (
              <span className="stat-value">
                {result.metrics.predicted_discharge.toLocaleString()} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>m³/s</span>
              </span>
            )}
          </div>
          <div className="flex justify-between">
            <div className="stat-box">
              <span className="stat-label">Qcrit (Threshold)</span>
              <span style={{ fontWeight: 'bold' }}>
                {result ? (result.metrics.qcrit === 'NOT_CONFIGURED' ? 'NOT CONFIGURED' : `${result.metrics.qcrit} m³/s`) : '900 m³/s (Prototype)'}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Stage</span>
              <span style={{ fontWeight: 'bold' }}>
                {result ? (result.metrics.stage_m === 'NOT_CONFIGURED' ? 'NOT CONFIGURED' : `${result.metrics.stage_m} m`) : '0.00 m'}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">dQ/dt</span>
              <span style={{ fontWeight: 'bold' }}>
                {result ? (result.metrics.dq_dt === 'NOT_CONFIGURED' ? 'NOT CONFIGURED' : `${result.metrics.dq_dt} m³/s²`) : '0.000 m³/s²'}
              </span>
            </div>
          </div>
          <div>
            <div className="flex justify-between" style={{ marginBottom: '4px', fontSize: '0.875rem' }}>
              <span>Capacity Utilization</span>
              <span className={isWarning ? 'text-warning' : 'text-normal'} style={{ fontWeight: 600 }}>
                {result ? (result.metrics.capacity_utilization === 'NOT_CONFIGURED' || result.metrics.capacity_utilization === 0 ? '0.0%' : `${result.metrics.capacity_utilization}%`) : '0.0%'}
              </span>
            </div>
            <div style={{ height: '6px', background: 'var(--bg-main)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: result && typeof result.metrics.capacity_utilization === 'number' ? `${Math.min(100, result.metrics.capacity_utilization)}%` : '0%', background: isWarning ? 'var(--status-warning)' : 'var(--status-normal)', transition: 'var(--transition)' }}></div>
            </div>
          </div>
          <div className="text-muted" style={{ fontSize: '0.875rem', background: 'var(--bg-main)', padding: '10px', borderRadius: '6px' }}>
            <div>Simulation Status: <strong>{simulationStatus}</strong></div>
            <div>Data Mode: <strong className={dataMode === 'SIMULATION' ? 'text-watch' : 'text-normal'}>{dataMode} (PROTOTYPE)</strong></div>
            {result?.provenance && (
              <div style={{ marginTop: '4px', fontSize: '0.75rem', color: '#64748B' }}>
                Engine: {result.provenance.model || 'ST-GNN-v1.0'}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Real-Time Prediction Chart */}
      <div className="card" style={{ gridColumn: 'span 4', gridRow: 'span 4' }}>
        <div className="card-header flex justify-between items-center">
          <span className="card-title">Runoff & Discharge Hydrograph</span>
          {result && <span style={{ fontSize: '0.75rem', color: '#F59E0B' }}>SIMULATED SCENARIO</span>}
        </div>
        {result && result.timeseries && result.timeseries.length > 0 ? (
          <div style={{ width: '100%', height: '100%', minHeight: '200px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="time" stroke="#94A3B8" fontSize={12} />
                <YAxis stroke="#94A3B8" fontSize={12} label={{ value: 'm³/s', angle: -90, position: 'insideLeft', fill: '#94A3B8' }} />
                <Tooltip contentStyle={{ backgroundColor: '#151A27', borderColor: '#334155' }} />
                <Legend />
                {typeof result.metrics.qcrit === 'number' && (
                  <ReferenceLine y={result.metrics.qcrit} label="Qcrit (900 m³/s, Prototype Assumption)" stroke="#EF4444" strokeDasharray="3 3" />
                )}
                <Line type="monotone" dataKey="discharge" stroke="#38BDF8" strokeWidth={2} dot={false} name="Runoff Q" />
                <Line type="monotone" dataKey="predicted" stroke="#F59E0B" strokeWidth={3} dot={{ r: 6 }} name="Predicted Peak Q" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="flex items-center justify-center text-center" style={{ height: '100%', color: 'var(--text-muted)', padding: '16px' }}>
            {dataMode === 'REAL'
              ? 'WAITING FOR REAL DATA (IMD AWS & CWC Sensors Not Configured)'
              : (isSimulating ? 'Processing simulation pipeline...' : 'Select a scenario above and click Start Simulation to generate predictions.')}
          </div>
        )}
      </div>

      <div className="card" style={{ gridColumn: 'span 4', gridRow: 'span 3' }}>
        <div className="card-header">
          <span className="card-title">Catchment Summary (Chungthang)</span>
        </div>
        <div className="flex" style={{ flexDirection: 'column', gap: '12px', fontSize: '0.875rem' }}>
          <div className="flex justify-between items-center">
            <span>Peak Runoff Volume</span>
            <span style={{ fontWeight: 'bold' }}>
              {result && result.metrics.peak_runoff_volume !== 'NOT_CONFIGURED' ? `${result.metrics.peak_runoff_volume.toLocaleString()} m³` : 'Ready to compute'}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span>Soil Moisture (AMC)</span>
            <span style={{ fontWeight: 'bold' }}>{result ? result.metrics.amc : 'AMC-II (Average)'}</span>
          </div>
          <div className="flex justify-between items-center">
            <span>Total Rainfall</span>
            <span style={{ fontWeight: 'bold' }}>
              {result && result.timeseries && result.timeseries.length > 0
                ? `${result.timeseries.reduce((sum, t) => sum + t.rainfall_mm, 0).toFixed(1)} mm`
                : 'Scenario dependent'}
            </span>
          </div>
        </div>
      </div>

    </div>
  );
}
