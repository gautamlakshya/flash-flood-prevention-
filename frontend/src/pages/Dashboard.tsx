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
  const { result, simulationStatus, isSimulating } = useAppStore();
  const isWarning = result?.metrics?.hazard === 'FLASH FLOOD WARNING';

  const formatChartData = () => {
    if (!result || !result.timeseries) return [];
    
    // We have runoff volumes and need to show discharge approach towards Qcrit
    // We'll map the timeseries to show the runoff scaling up to the predicted discharge
    const data = result.timeseries.map((t, idx) => {
      // In the backend simulator, we take runoff volume / 900 for q.
      // But we just want to show a nice trend culminating in the predicted Q.
      const q = t.runoff_volume_m3 / 900; 
      
      return {
        time: t.timestamp ? new Date(t.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : `T+${idx}`,
        discharge: q,
        predicted: idx === result.timeseries.length - 1 ? result.metrics.predicted_discharge : null
      };
    });

    return data;
  };

  const chartData = formatChartData();

  return (
    <div className="dashboard-grid">
      {/* Map Layer */}
      <div className="map-container">
        <div style={{ position: 'absolute', top: '16px', left: '16px', zIndex: 10, background: 'var(--bg-panel)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <h3 className="card-title" style={{ marginBottom: '8px', border: 'none', padding: 0 }}>Map Layers</h3>
          <div className="flex" style={{ flexDirection: 'column', gap: '8px', fontSize: '0.875rem' }}>
            <label className="flex items-center gap-2"><input type="checkbox" defaultChecked /> Flood Hazard</label>
            <label className="flex items-center gap-2"><input type="checkbox" defaultChecked /> River Network</label>
            <label className="flex items-center gap-2"><input type="checkbox" defaultChecked /> Rainfall (INSAT)</label>
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
            <span className="alert-badge alert-warning">FLASH FLOOD WARNING</span>
          ) : (
            <span className="alert-badge alert-normal">{result?.metrics?.hazard || 'NORMAL'}</span>
          )}
        </div>
        <div className="flex" style={{ flexDirection: 'column', gap: '16px' }}>
          <div className="stat-box">
            <span className="stat-label">Predicted Peak Discharge (Chungthang)</span>
            {result?.metrics?.predicted_discharge === 'NOT_CONFIGURED' || !result ? (
              <span className="stat-value" style={{ fontSize: '1rem', color: '#94A3B8' }}>NOT CONFIGURED</span>
            ) : (
              <span className="stat-value">{result.metrics.predicted_discharge.toLocaleString()} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>m³/s</span></span>
            )}
          </div>
          <div className="flex justify-between">
            <div className="stat-box">
              <span className="stat-label">Qcrit</span>
              <span style={{ fontWeight: 'bold' }}>
                {result ? (result.metrics.qcrit === 'NOT_CONFIGURED' ? 'NOT CONFIGURED' : `${result.metrics.qcrit} m³/s`) : '---'}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Stage</span>
              <span style={{ fontWeight: 'bold' }}>
                {result ? (result.metrics.stage_m === 'NOT_CONFIGURED' ? 'NOT CONFIGURED' : `${result.metrics.stage_m} m`) : '---'}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">dQ/dt</span>
              <span style={{ fontWeight: 'bold' }}>{result ? (result.metrics.dq_dt === 'NOT_CONFIGURED' ? 'NOT CONFIGURED' : `${result.metrics.dq_dt} m³/s²`) : '---'}</span>
            </div>
          </div>
          <div>
            <div className="flex justify-between" style={{ marginBottom: '4px', fontSize: '0.875rem' }}>
              <span>Capacity Utilization</span>
              <span className={isWarning ? 'text-warning' : 'text-normal'} style={{ fontWeight: 600 }}>
                {result ? (result.metrics.capacity_utilization === 'NOT_CONFIGURED' || result.metrics.capacity_utilization === 0 ? 'NOT CONFIGURED' : `${result.metrics.capacity_utilization}%`) : '---'}
              </span>
            </div>
            <div style={{ height: '6px', background: 'var(--bg-main)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: result && typeof result.metrics.capacity_utilization === 'number' ? `${Math.min(100, result.metrics.capacity_utilization)}%` : '0%', background: isWarning ? 'var(--status-warning)' : 'var(--status-normal)', transition: 'var(--transition)' }}></div>
            </div>
          </div>
          <div className="text-muted" style={{ fontSize: '0.875rem' }}>
            Simulation Status: <strong>{simulationStatus}</strong>
            <br />
            Data Mode: <strong>{result?.data_mode || 'SIMULATION'}</strong>
          </div>
        </div>
      </div>
      
      {/* Real-Time Prediction Chart */}
      <div className="card" style={{ gridColumn: 'span 4', gridRow: 'span 4' }}>
        <div className="card-header">
          <span className="card-title">Prediction Chart</span>
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
                  <ReferenceLine y={result.metrics.qcrit} label="Qcrit" stroke="#EF4444" strokeDasharray="3 3" />
                )}
                <Line type="monotone" dataKey="discharge" stroke="#3B82F6" strokeWidth={2} dot={false} name="Runoff Q" />
                <Line type="monotone" dataKey="predicted" stroke="#F59E0B" strokeWidth={3} dot={{ r: 6 }} name="Predicted Peak Q" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="flex items-center justify-center" style={{ height: '100%', color: 'var(--text-muted)' }}>
            {result?.data_mode === 'REAL' ? 'WAITING FOR REAL DATA (NOT CONFIGURED)' : (isSimulating ? 'Loading data...' : 'Run simulation to view chart')}
          </div>
        )}
      </div>

      <div className="card" style={{ gridColumn: 'span 4', gridRow: 'span 3' }}>
        <div className="card-header">
          <span className="card-title">Current Conditions Summary</span>
        </div>
        <div className="flex" style={{ flexDirection: 'column', gap: '12px', fontSize: '0.875rem' }}>
          <div className="flex justify-between items-center">
            <span>Peak Runoff Volume</span>
            <span style={{ fontWeight: 'bold' }}>{result && result.metrics.peak_runoff_volume !== 'NOT_CONFIGURED' ? `${result.metrics.peak_runoff_volume.toLocaleString()} m³` : 'NOT CONFIGURED'}</span>
          </div>
          <div className="flex justify-between items-center">
            <span>Soil Moisture (AMC)</span>
            <span style={{ fontWeight: 'bold' }}>{result ? result.metrics.amc : '---'}</span>
          </div>
          <div className="flex justify-between items-center">
            <span>Total Rainfall</span>
            <span style={{ fontWeight: 'bold' }}>
              {result && result.timeseries && result.timeseries.length > 0 ? `${result.timeseries.reduce((sum, t) => sum + t.rainfall_mm, 0).toFixed(1)} mm` : 'NOT CONFIGURED'}
            </span>
          </div>
        </div>
      </div>
      
    </div>
  );
}
