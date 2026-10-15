import { useEffect, useState } from 'react';
import { Database, Info } from 'lucide-react';

interface DataSourceStatus {
  name: string;
  type: string;
  status: string;
  last_updated: string | null;
  error: string | null;
}

export default function DataSources() {
  const [sources, setSources] = useState<DataSourceStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    const apiUrl = ((import.meta as any).env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
    fetch(`${apiUrl}/api/v1/data_sources`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setSources(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(e => {
        console.error("Failed to fetch data sources:", e);
        setFetchError("Unable to reach backend telemetry audit. Showing local baseline registry.");
        // Fallback honest registry so page is never blank
        setSources([
          { name: "ISRO CartoDEM (30m cdnh45w.tif)", type: "DEM", status: "AVAILABLE LOCALLY", last_updated: null, error: null },
          { name: "SRTM 30m DEM (N27E088 / N28E088)", type: "DEM", status: "AVAILABLE LOCALLY", last_updated: null, error: null },
          { name: "IMD AWS API (Precipitation)", type: "HYDROMET", status: "NOT CONFIGURED", last_updated: null, error: "Requires IMD API credentials" },
          { name: "CWC Historical Discharge Telemetry", type: "HYDROLOGY", status: "NOT CONFIGURED", last_updated: null, error: "Historical gauge CSV pending field deployment" },
          { name: "Sentinel-1 SAR Backscatter (Soil Moisture)", type: "SOIL_MOISTURE", status: "NOT CONFIGURED", last_updated: null, error: "Requires Copernicus Data Space credentials" },
          { name: "GSI Bhukosh Landslide Inventory", type: "HAZARD_CONTEXT", status: "NOT CONFIGURED", last_updated: null, error: "Shapefile export not present in data/raw/landslides/" },
          { name: "Synthetic Weather & Hydro Generator", type: "SIMULATION_ENGINE", status: "CONNECTED", last_updated: new Date().toISOString(), error: null }
        ]);
        setLoading(false);
      });
  }, []);

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="flex justify-between items-center">
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Data Sources & Telemetry Infrastructure</h2>
          <p className="text-muted" style={{ fontSize: '0.875rem', marginTop: '4px' }}>
            Live status of geospatial terrain assets, satellite feeds, and hydrometric observations
          </p>
        </div>
      </div>

      {fetchError && (
        <div style={{ background: 'rgba(234, 179, 8, 0.1)', border: '1px solid #CA8A04', padding: '12px 16px', borderRadius: '8px', color: '#FACC15', fontSize: '0.875rem' }}>
          ⚠️ {fetchError}
        </div>
      )}

      {/* Overview Card */}
      <div className="card">
        <div className="card-header flex items-center gap-2">
          <Info size={18} className="text-normal" />
          <span className="card-title">Multi-Source Ingestion Architecture</span>
        </div>
        <p className="text-muted" style={{ fontSize: '0.9rem', lineHeight: '1.6' }}>
          The Flash Flood Early Warning System operates in two distinct data modes:
          <br />
          • <strong>Simulation Mode (Active):</strong> Uses deterministic hydrological scenarios (e.g. Extreme Cloudburst, GLOF) calibrated to the Chungthang, Sikkim watershed using real SRTM/CartoDEM 30m terrain models.
          <br />
          • <strong>Real Telemetry Mode:</strong> Connects to operational weather station feeds and river gauges once deployed in the field with authorized API credentials.
        </p>
      </div>

      <div className="dashboard-grid" style={{ height: 'auto', padding: 0 }}>
        <div className="card" style={{ gridColumn: 'span 12' }}>
          <div className="card-header flex justify-between items-center">
            <span className="card-title">Data Providers Status</span>
            <span className="text-muted" style={{ fontSize: '0.85rem' }}>Total Sources: {sources.length}</span>
          </div>

          {loading ? (
            <div style={{ padding: '32px', color: 'var(--text-muted)', textAlign: 'center' }}>
              Auditing data sources and local terrain assets...
            </div>
          ) : (
            <div className="flex" style={{ flexDirection: 'column', gap: '16px', marginTop: '8px' }}>
              {sources.map((source, i) => {
                const isOperational = source.status === 'CONNECTED' || source.status === 'AVAILABLE LOCALLY';
                const isSim = source.status === 'SIMULATED';

                return (
                  <div key={i} className="flex items-center justify-between border-b pb-4" style={{ borderBottom: i < sources.length - 1 ? '1px solid var(--border-color)' : 'none' }}>
                    <div className="flex items-center gap-4">
                      <Database size={24} className={isOperational ? 'text-normal' : (isSim ? 'text-watch' : 'text-muted')} />
                      <div>
                        <div style={{ fontWeight: 600 }}>{source.name}</div>
                        <div className="text-muted" style={{ fontSize: '0.875rem', marginTop: '2px' }}>
                          Type: <strong>{source.type}</strong> | Last Updated: {source.last_updated ? new Date(source.last_updated).toLocaleString() : 'Never / Static'}
                        </div>
                        {source.error && (
                          <div className="text-warning" style={{ fontSize: '0.75rem', marginTop: '4px' }}>
                            Note: {source.error}
                          </div>
                        )}
                      </div>
                    </div>
                    <div>
                      <span className={`alert-badge ${
                        isOperational ? 'alert-normal' : (isSim ? 'alert-watch' : '')
                      }`} style={!isOperational && !isSim ? { backgroundColor: '#1E293B', color: '#94A3B8', borderColor: '#334155' } : {}}>
                        {source.status}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
