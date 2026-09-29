import { create } from 'zustand';

export interface SimulationResult {
  run_id: string;
  scenario: string;
  model_version: string;
  data_mode?: string;
  metrics: {
    predicted_discharge: any;
    qcrit: any;
    capacity_utilization: any;
    hazard: any;
    stage_m: any;
    peak_runoff_volume: any;
    cn: any;
    s_mm: any;
    amc: any;
    dq_dt: any;
    flooded_cells: any;
    inundation_polygons: any;
  };
  timeseries: Array<{
    rainfall_mm: number;
    runoff_depth_mm: number;
    runoff_volume_m3: number;
    cn: number;
    s_mm: number;
    timestamp: string;
  }>;
  inundation_geojson: any;
  cap_xml: string;
  provenance?: {
    dem: string;
    hydrology: string;
    rainfall: string;
    model: string;
  };
}

interface AppState {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  scenario: string;
  setScenario: (scenario: string) => void;
  
  dataMode: string;
  setDataMode: (mode: string) => void;
  
  isSimulating: boolean;
  simulationStatus: string;
  result: SimulationResult | null;
  error: string | null;
  
  startSimulation: () => Promise<void>;
  reset: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  activeTab: 'dashboard',
  setActiveTab: (tab) => set({ activeTab: tab }),
  
  scenario: 'Extreme Cloudburst',
  setScenario: (scenario) => set({ scenario }),
  
  dataMode: 'SIMULATION',
  setDataMode: (mode) => set({ dataMode: mode }),
  
  isSimulating: false,
  simulationStatus: 'Idle',
  result: null,
  error: null,
  
  startSimulation: async () => {
    const { scenario, dataMode, isSimulating } = get();
    if (isSimulating) return;
    
    set({ 
      isSimulating: true, 
      simulationStatus: 'Initializing...', 
      result: null,
      error: null
    });
    
    try {
      const res = await fetch(`${(import.meta as any).env.VITE_API_URL || 'http://localhost:8000'}/api/v1/simulation/start?scenario=${encodeURIComponent(scenario)}&data_mode=${encodeURIComponent(dataMode)}`, {
        method: 'POST',
      });
      
      if (!res.ok) {
        throw new Error('Backend connection unavailable');
      }
      
      const data = await res.json();
      const runId = data.run_id;
      
      // Poll
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`${(import.meta as any).env.VITE_API_URL || 'http://localhost:8000'}/api/v1/simulation/${runId}/status`);
          if (!statusRes.ok) throw new Error('Failed to get status');
          const statusData = await statusRes.json();
          set({ simulationStatus: 'Pipeline: ' + statusData.status });
          
          if (statusData.status === 'COMPLETED' || statusData.status === 'FAILED') {
            clearInterval(pollInterval);
            
            if (statusData.status === 'COMPLETED') {
              const resultsRes = await fetch(`${(import.meta as any).env.VITE_API_URL || 'http://localhost:8000'}/api/v1/simulation/${runId}/results`);
              if (!resultsRes.ok) throw new Error('Failed to get results');
              const resultsData = await resultsRes.json();
              set({ 
                isSimulating: false,
                simulationStatus: `Alert Generated: ${resultsData.metrics.hazard}`,
                result: resultsData
              });
            } else {
              set({ 
                isSimulating: false,
                simulationStatus: 'Simulation Failed',
                error: 'Simulation failed during execution'
              });
            }
          }
        } catch (e: any) {
          clearInterval(pollInterval);
          set({ 
            isSimulating: false, 
            simulationStatus: 'Error',
            error: e.message || 'Error connecting to backend'
          });
        }
      }, 1000);
      
    } catch (e: any) {
      set({ 
        isSimulating: false, 
        simulationStatus: 'Error',
        error: e.message || 'Backend connection unavailable'
      });
    }
  },
  
  reset: () => set({ result: null, error: null, simulationStatus: 'Idle' })
}));
