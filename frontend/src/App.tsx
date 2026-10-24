import { Activity, Map as MapIcon, ShieldAlert, Database, Signal, CloudRain, Navigation, ChevronLeft, ChevronRight } from 'lucide-react';
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
    startSimulation,
    sidebarCollapsed, toggleSidebar
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
      <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          {!sidebarCollapsed ? (
            <div className="brand">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity className="text-accent-blue" size={24} />
                <div style={{ fontWeight: 700, fontSize: '1.15rem', letterSpacing: '0.5px' }}>CHUNGTHANG</div>
              </div>
              <div className="brand-subtitle">Teesta River | Mangan, Sikkim</div>
            </div>
          ) : (
            <div className="brand-collapsed" title="Chungthang Flash Flood Early Warning System">
              <Activity className="text-accent-blue" size={26} />
            </div>
          )}
          <button
            className="sidebar-toggle-btn"
            onClick={toggleSidebar}
            title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>
        
        <nav className="nav-menu">
          <a
            href="#"
            className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={(e) => { e.preventDefault(); setActiveTab('dashboard'); }}
            title={sidebarCollapsed ? "Dashboard" : undefined}
          >
            <MapIcon size={20} />
            {!sidebarCollapsed && <span>Dashboard</span>}
          </a>
          <a
            href="#"
            className={`nav-item ${activeTab === 'alerts' ? 'active' : ''}`}
            onClick={(e) => { e.preventDefault(); setActiveTab('alerts'); }}
            title={sidebarCollapsed ? "Active Alerts" : undefined}
          >
            <ShieldAlert size={20} />
            {!sidebarCollapsed && <span>Active Alerts</span>}
          </a>
          <a
            href="#"
            className={`nav-item ${activeTab === 'hydrology' ? 'active' : ''}`}
            onClick={(e) => { e.preventDefault(); setActiveTab('hydrology'); }}
            title={sidebarCollapsed ? "Hydrology" : undefined}
          >
            <CloudRain size={20} />
            {!sidebarCollapsed && <span>Hydrology</span>}
          </a>
          <a
            href="#"
            className={`nav-item ${activeTab === 'predictions' ? 'active' : ''}`}
            onClick={(e) => { e.preventDefault(); setActiveTab('predictions'); }}
            title={sidebarCollapsed ? "AI Predictions" : undefined}
          >
            <Activity size={20} />
            {!sidebarCollapsed && <span>AI Predictions</span>}
          </a>
          <a
            href="#"
            className={`nav-item ${activeTab === 'field' ? 'active' : ''}`}
            onClick={(e) => { e.preventDefault(); setActiveTab('field'); }}
            title={sidebarCollapsed ? "Field Ops" : undefined}
          >
            <Navigation size={20} />
            {!sidebarCollapsed && <span>Field Ops</span>}
          </a>
          <a
            href="#"
            className={`nav-item ${activeTab === 'data' ? 'active' : ''}`}
            onClick={(e) => { e.preventDefault(); setActiveTab('data'); }}
            title={sidebarCollapsed ? "Data Sources" : undefined}
          >
            <Database size={20} />
            {!sidebarCollapsed && <span>Data Sources</span>}
          </a>
        </nav>
        
        <div className="sidebar-footer">
          {!sidebarCollapsed ? (
            <div className="stat-box" style={{ padding: '8px 12px' }}>
              <div className="stat-label flex items-center justify-between" style={{ fontSize: '0.75rem' }}>
                System Status
                <span className="flex items-center gap-2 text-normal">
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--status-normal)' }}></span> ONLINE
                </span>
              </div>
            </div>
          ) : (
            <div
              className="stat-box-collapsed"
              title="System Status: ONLINE (Operational)"
              style={{ display: 'flex', justifyContent: 'center', padding: '8px 0' }}
            >
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: 'var(--status-normal)', boxShadow: '0 0 8px #10B981' }}></span>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content" style={{ overflowY: 'auto' }}>
        <header className="app-header" style={{ position: 'sticky', top: 0, zIndex: 50, padding: '0 20px' }}>
          <div className="flex items-center gap-3">
            <h1 style={{ fontSize: '1.15rem', fontWeight: 700, letterSpacing: '0.3px', margin: 0 }}>Command Center</h1>
            {isWarning && <span className="alert-badge alert-warning animate-in" style={{ fontSize: '0.7rem' }}>FLASH FLOOD WARNING</span>}
            {error && <span className="alert-badge alert-warning animate-in" style={{ fontSize: '0.7rem' }}>ERROR: {error}</span>}
          </div>
          
          <div className="flex items-center gap-3 flex-wrap">
            <select 
              value={useAppStore(s => s.dataMode)} 
              onChange={(e) => useAppStore.getState().setDataMode(e.target.value)} 
              disabled={isSimulating}
              style={{ background: 'var(--bg-main)', color: 'var(--text-main)', border: '1px solid var(--border-color)', padding: '5px 10px', borderRadius: '6px', fontSize: '0.8rem', fontWeight: 500 }}
            >
              <option value="SIMULATION">MODE: SIMULATED PROTOTYPE</option>
              <option value="REAL">MODE: REAL DATA</option>
            </select>
            <select 
              value={scenario} 
              onChange={(e) => setScenario(e.target.value)} 
              disabled={isSimulating}
              style={{ background: 'var(--bg-main)', color: 'var(--text-main)', border: '1px solid var(--border-color)', padding: '5px 10px', borderRadius: '6px', fontSize: '0.8rem', fontWeight: 500 }}
            >
              <option value="Normal Monsoon">Normal Monsoon</option>
              <option value="Extreme Cloudburst">Extreme Cloudburst</option>
            </select>
            <div className="text-muted" style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Signal size={14} style={{ color: '#10B981' }} />
              <span>Last sync: Just now</span>
            </div>
            <button
              className="btn btn-primary"
              onClick={startSimulation}
              disabled={isSimulating}
              style={{ padding: '6px 14px', fontSize: '0.8rem', fontWeight: 600 }}
            >
              {isSimulating ? 'Simulating...' : 'Start Simulation'}
            </button>
          </div>
        </header>
        
        {renderContent()}
      </main>
    </div>
  );
}

export default App;
