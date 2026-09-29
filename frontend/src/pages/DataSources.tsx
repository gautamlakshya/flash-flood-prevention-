import { useEffect, useState } from 'react';
import { Database } from 'lucide-react';

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

  useEffect(() => {
    fetch(`${(import.meta as any).env.VITE_API_URL || 'http://localhost:8000'}/api/v1/data_sources`)
      .then(res => res.json())
      .then(data => {
        setSources(data);
        setLoading(false);
      })
      .catch(e => {
        console.error("Failed to fetch data sources:", e);
        setLoading(false);
      });
  }, []);

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="flex items-center gap-4">
        <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Data Sources & Infrastructure</h2>
      </div>

      <div className="dashboard-grid" style={{ height: 'auto', padding: 0 }}>
        <div className="card" style={{ gridColumn: 'span 12' }}>
          {loading ? (
            <div style={{ padding: '24px', color: 'var(--text-muted)' }}>Loading live data sources...</div>
          ) : (
            <div className="flex" style={{ flexDirection: 'column', gap: '16px' }}>
              {sources.map((source, i) => (
                <div key={i} className="flex items-center justify-between border-b pb-4" style={{ borderBottom: i < sources.length - 1 ? '1px solid var(--border-color)' : 'none' }}>
                  <div className="flex items-center gap-4">
                    <Database size={24} className={
                      source.status === 'CONNECTED' || source.status === 'AVAILABLE LOCALLY' ? 'text-normal' : 
                      source.status === 'SIMULATED' ? 'text-watch' : 'text-muted'
                    } />
                    <div>
                      <div style={{ fontWeight: 600 }}>{source.name}</div>
                      <div className="text-muted" style={{ fontSize: '0.875rem' }}>Type: {source.type} | Last Updated: {source.last_updated ? new Date(source.last_updated).toLocaleString() : 'Never'}</div>
                      {source.error && <div className="text-warning" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Error: {source.error}</div>}
                    </div>
                  </div>
                  <div>
                    <span className={`alert-badge ${
                      source.status === 'CONNECTED' || source.status === 'AVAILABLE LOCALLY' ? 'alert-normal' : 
                      source.status === 'SIMULATED' ? 'alert-watch' : 'alert-normal'
                    }`} style={source.status === 'NOT CONFIGURED' || source.status === 'ERROR' ? { backgroundColor: '#1E293B', color: '#94A3B8', borderColor: '#334155' } : {}}>
                      {source.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
