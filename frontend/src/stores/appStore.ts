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
      const apiUrl = ((import.meta as any).env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
      const res = await fetch(`${apiUrl}/api/v1/simulation/start?scenario=${encodeURIComponent(scenario)}&data_mode=${encodeURIComponent(dataMode)}`, {
        method: 'POST',
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();
      const runId = data.run_id;
      let pollCount = 0;
      const MAX_POLLS = 30; // 30 seconds maximum

      // Poll
      const pollInterval = setInterval(async () => {
        pollCount++;
        if (pollCount > MAX_POLLS) {
          clearInterval(pollInterval);
          set({
            isSimulating: false,
            simulationStatus: 'Timed Out',
            error: 'Simulation pipeline timed out after 30 seconds.'
          });
          return;
        }

        try {
          const statusRes = await fetch(`${apiUrl}/api/v1/simulation/${runId}/status`);
          if (!statusRes.ok) {
            const errData = await statusRes.json().catch(() => ({}));
            throw new Error(errData.detail || 'Failed to get simulation status');
          }
          const statusData = await statusRes.json();
          set({ simulationStatus: 'Pipeline: ' + statusData.status });

          if (statusData.status === 'COMPLETED' || statusData.status === 'FAILED') {
            clearInterval(pollInterval);

            if (statusData.status === 'COMPLETED') {
              const resultsRes = await fetch(`${apiUrl}/api/v1/simulation/${runId}/results`);
              if (!resultsRes.ok) {
                const errData = await resultsRes.json().catch(() => ({}));
                throw new Error(errData.detail || 'Failed to retrieve simulation results');
              }
              const resultsData = await resultsRes.json();
              set({
                isSimulating: false,
                simulationStatus: `Completed: ${resultsData.metrics.hazard}`,
                result: resultsData,
                error: null
              });
            } else {
              set({
                isSimulating: false,
                simulationStatus: 'Simulation Failed',
                error: 'Simulation pipeline reported failure state'
              });
            }
          }
        } catch (e: any) {
          clearInterval(pollInterval);
          set({
            isSimulating: false,
            simulationStatus: 'Error',
            error: e.message || 'Error communicating with backend'
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
