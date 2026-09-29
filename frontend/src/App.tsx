import { Activity, Map as MapIcon, ShieldAlert, Database, Signal, Settings, CloudRain, Navigation } from 'lucide-react';
import { useAppStore } from './stores/appStore';

import Dashboard from './pages/Dashboard';
import Hydrology from './pages/Hydrology';
import Predictions from './pages/Predictions';
import ActiveAlerts from './pages/ActiveAlerts';
import DataSources from './pages/DataSources';
import FieldOps from './pages/FieldOps';

function App() {
  const { 
    activeTab, setActiveTab, 
    scenario, setScenario, 
    isSimulating, result, error,
    startSimulation 
  } = useAppStore();

  const isWarning = result?.metrics?.hazard === 'FLASH FLOOD WARNING';

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard': return <Dashboard />;
      case 'hydrology': return <Hydrology />;
      case 'predictions': return <Predictions />;
      case 'alerts': return <ActiveAlerts />;
      case 'data': return <DataSources />;
      case 'field': return <FieldOps />;
      default: return <Dashboard />;
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="app-header" style={{ justifyContent: 'center' }}>
          <div className="brand" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Activity className="text-accent-blue" size={24} />
              <div style={{ fontWeight: 700, fontSize: '1.25rem' }}>CHUNGTHANG</div>
            </div>
            <div className="brand-subtitle" style={{ marginTop: '4px' }}>Teesta River | Mangan, Sikkim</div>
          </div>
        </div>
        
        <nav className="nav-menu">
          <a href="#" className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('dashboard'); }}>
            <MapIcon size={20} /> Dashboard
          </a>
          <a href="#" className={`nav-item ${activeTab === 'alerts' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('alerts'); }}>
            <ShieldAlert size={20} /> Active Alerts
          </a>
          <a href="#" className={`nav-item ${activeTab === 'hydrology' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('hydrology'); }}>
            <CloudRain size={20} /> Hydrology
          </a>
          <a href="#" className={`nav-item ${activeTab === 'predictions' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('predictions'); }}>
            <Activity size={20} /> AI Predictions
          </a>
          <a href="#" className={`nav-item ${activeTab === 'field' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('field'); }}>
            <Navigation size={20} /> Field Ops
          </a>
          <a href="#" className={`nav-item ${activeTab === 'data' ? 'active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('data'); }}>
            <Database size={20} /> Data Sources
          </a>
        </nav>
        
        <div style={{ padding: '24px 16px', borderTop: '1px solid var(--border-color)' }}>
          <div className="stat-box">
            <div className="stat-label flex items-center justify-between">
              System Status 
              <span className="flex items-center gap-2 text-normal">
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--status-normal)' }}></span> ONLINE
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content" style={{ overflowY: 'auto' }}>
        <header className="app-header" style={{ position: 'sticky', top: 0, zIndex: 50 }}>
          <div className="flex items-center gap-4">
            <h1 style={{ fontSize: '1.2rem', fontWeight: 600 }}>Command Center</h1>
            {isWarning && <span className="alert-badge alert-warning animate-in">FLASH FLOOD WARNING</span>}
            {error && <span className="alert-badge alert-warning animate-in">ERROR: {error}</span>}
          </div>
          
          <div className="flex items-center gap-4">
            <select 
              value={useAppStore(s => s.dataMode)} 
              onChange={(e) => useAppStore.getState().setDataMode(e.target.value)} 
              disabled={isSimulating}
              style={{ background: 'var(--bg-panel)', color: 'var(--text-main)', border: '1px solid var(--border-color)', padding: '6px 12px', borderRadius: '4px' }}
            >
              <option value="SIMULATION">MODE: SIMULATED PROTOTYPE</option>
              <option value="REAL">MODE: REAL DATA</option>
            </select>
            <select 
              value={scenario} 
              onChange={(e) => setScenario(e.target.value)} 
              disabled={isSimulating}
              style={{ background: 'var(--bg-panel)', color: 'var(--text-main)', border: '1px solid var(--border-color)', padding: '6px 12px', borderRadius: '4px' }}
            >
              <option value="Normal Monsoon">Normal Monsoon</option>
              <option value="Extreme Cloudburst">Extreme Cloudburst</option>
            </select>
            <div className="text-muted" style={{ fontSize: '0.875rem' }}>
              <Signal size={16} style={{ display: 'inline', verticalAlign: 'text-bottom', marginRight: '4px' }} />
              Last sync: Just now
            </div>
            <button className="btn btn-primary" onClick={startSimulation} disabled={isSimulating}>
              {isSimulating ? 'Simulating...' : 'Start Simulation'}
            </button>
            <button className="btn">
              <Settings size={18} />
            </button>
          </div>
        </header>
        
        {renderContent()}
      </main>
    </div>
  );
}

export default App;
