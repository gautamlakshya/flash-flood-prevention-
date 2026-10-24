import React, { useEffect, useRef, useState, useCallback } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useAppStore } from '../stores/appStore';
import {
  Layers,
  Maximize2,
  Minimize2,
  Info,
  Eye,
  EyeOff
} from 'lucide-react';

interface FloodMapProps {
  isWarning: boolean;
  inundationGeoJSON?: any;
  activeAlert?: any;
  rainfallData?: any;
}

type BasemapType = 'dark' | 'topo' | 'satellite';

const CHUNGTHANG_CENTER: [number, number] = [88.6500, 27.5950];
const CATCHMENT_BOUNDS: [[number, number], [number, number]] = [
  [88.1171, 27.5699], // southwest
  [88.8882, 28.1268]  // northeast
];

const BASEMAP_STYLES: Record<BasemapType, any> = {
  dark: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  topo: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  satellite: {
    version: 8,
    sources: {
      'esri-satellite': {
        type: 'raster',
        tiles: [
          'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
        ],
        tileSize: 256,
        attribution: 'Tiles &copy; Esri, Maxar, Earthstar Geographics'
      }
    },
    layers: [
      {
        id: 'esri-satellite-layer',
        type: 'raster',
        source: 'esri-satellite',
        minzoom: 0,
        maxzoom: 19
      }
    ]
  }
};

const FloodMap: React.FC<FloodMapProps> = ({
  isWarning,
  inundationGeoJSON,
  activeAlert,
  rainfallData
}) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);

  const { dataMode } = useAppStore();

  const [mapLoaded, setMapLoaded] = useState(false);
  const [activeBasemap, setActiveBasemap] = useState<BasemapType>('dark');
  const [showLegend, setShowLegend] = useState(true);
  const [showControls, setShowControls] = useState(false);

  // Layer Visibility states
  const [layerVisibility, setLayerVisibility] = useState({
    catchment: true,
    streams: true,
    locations: true,
    inundation: true
  });

  // Cached data
  const [catchmentData, setCatchmentData] = useState<any>(null);
  const [streamsData, setStreamsData] = useState<any>(null);
  const [locationsData, setLocationsData] = useState<any>(null);
  const [terrainMeta, setTerrainMeta] = useState<any>(null);

  const apiUrl = ((import.meta as any).env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

  // 1. Fetch real terrain layers from backend
  useEffect(() => {
    let isMounted = true;

    Promise.all([
      fetch(`${apiUrl}/api/v1/terrain/catchment`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${apiUrl}/api/v1/terrain/streams`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${apiUrl}/api/v1/terrain/locations`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${apiUrl}/api/v1/terrain/metadata`).then(r => r.ok ? r.json() : null).catch(() => null)
    ]).then(([catchment, streams, locations, meta]) => {
      if (!isMounted) return;
      if (catchment) setCatchmentData(catchment);
      if (streams) setStreamsData(streams);
      if (locations) setLocationsData(locations);
      if (meta) setTerrainMeta(meta);
    });

    return () => {
      isMounted = false;
    };
  }, [apiUrl]);

  // Determine effective hazard state
  const effectiveSeverity = activeAlert?.severity || (isWarning ? 'WARNING' : 'NORMAL');
  const isThreatActive = ['WATCH', 'WARNING', 'CRITICAL'].includes(effectiveSeverity);

  // Status HUD properties
  const hudSource = rainfallData?.source || (dataMode === 'SIMULATION' ? 'Synthetic Simulation Model' : 'Open-Meteo Forecast NWP');
  const hudType = rainfallData?.data_type || (dataMode === 'SIMULATION' ? 'SIMULATION' : 'FORECAST');
  const hudStatus = rainfallData?.is_fresh
    ? (hudType === 'FORECAST' ? 'FORECAST' : (hudType === 'OBSERVATION' ? 'LIVE' : 'ACTIVE'))
    : (rainfallData ? 'STALE' : (dataMode === 'SIMULATION' ? 'SIMULATION' : 'READY'));

  const validTimeStr = rainfallData?.latest_reading?.valid_time
    ? new Date(rainfallData.latest_reading.valid_time).toUTCString()
    : (activeAlert?.created_at ? new Date(activeAlert.created_at).toUTCString() : null);

  const retrievalTimeStr = rainfallData?.latest_reading?.retrieval_time
    ? new Date(rainfallData.latest_reading.retrieval_time).toLocaleTimeString()
    : null;

  // Add all layers helper
  const addGeospatialLayers = useCallback((currentMap: maplibregl.Map) => {
    // A. Catchment Watershed Layer
    if (catchmentData && !currentMap.getSource('catchment-source')) {
      currentMap.addSource('catchment-source', {
        type: 'geojson',
        data: catchmentData
      });

      currentMap.addLayer({
        id: 'catchment-fill',
        type: 'fill',
        source: 'catchment-source',
        layout: { visibility: layerVisibility.catchment ? 'visible' : 'none' },
        paint: {
          'fill-color': '#0284C7',
          'fill-opacity': 0.08
        }
      });

      currentMap.addLayer({
        id: 'catchment-line',
        type: 'line',
        source: 'catchment-source',
        layout: {
          'visibility': layerVisibility.catchment ? 'visible' : 'none',
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': '#0284C7',
          'line-width': 1.8,
          'line-dasharray': [4, 3],
          'line-opacity': 0.75
        }
      });
    }

    // B. River Network (SRTM 30m real stream lines)
    if (streamsData && !currentMap.getSource('streams-source')) {
      currentMap.addSource('streams-source', {
        type: 'geojson',
        data: streamsData
      });

      currentMap.addLayer({
        id: 'streams-layer',
        type: 'line',
        source: 'streams-source',
        layout: {
          'visibility': layerVisibility.streams ? 'visible' : 'none',
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': isThreatActive ? '#EF4444' : '#38BDF8',
          'line-width': isThreatActive ? 3.0 : 2.0,
          'line-opacity': 0.85
        }
      });
    }

    // C. Settlement & Critical Locations (Markers & Icons)
    if (locationsData && !currentMap.getSource('locations-source')) {
      currentMap.addSource('locations-source', {
        type: 'geojson',
        data: locationsData
      });

      // Outer halo for distinct operational outlet
      currentMap.addLayer({
        id: 'locations-halo',
        type: 'circle',
        source: 'locations-source',
        layout: { visibility: layerVisibility.locations ? 'visible' : 'none' },
        paint: {
          'circle-radius': [
            'case',
            ['==', ['get', 'category'], 'operational_outlet'], 12,
            ['==', ['get', 'category'], 'cwc_reference_station'], 10,
            ['==', ['get', 'category'], 'critical_infrastructure'], 11,
            8
          ],
          'circle-color': ['get', 'color'],
          'circle-opacity': 0.35
        }
      });

      // Core point
      currentMap.addLayer({
        id: 'locations-points',
        type: 'circle',
        source: 'locations-source',
        layout: { visibility: layerVisibility.locations ? 'visible' : 'none' },
        paint: {
          'circle-radius': [
            'case',
            ['==', ['get', 'category'], 'operational_outlet'], 7,
            ['==', ['get', 'category'], 'cwc_reference_station'], 6.5,
            5.5
          ],
          'circle-color': ['get', 'color'],
          'circle-stroke-width': 2,
          'circle-stroke-color': '#FFFFFF'
        }
      });

      // Labels
      currentMap.addLayer({
        id: 'locations-labels',
        type: 'symbol',
        source: 'locations-source',
        layout: {
          'visibility': layerVisibility.locations ? 'visible' : 'none',
          'text-field': ['get', 'name'],
          'text-size': 11,
          'text-offset': [0, 1.4],
          'text-anchor': 'top',
          'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold']
        },
        paint: {
          'text-color': '#F8FAFC',
          'text-halo-color': '#0F172A',
          'text-halo-width': 2
        }
      });
    }

    // D. 2D Flood Inundation Layer (when output exists)
    if (inundationGeoJSON && inundationGeoJSON.features && inundationGeoJSON.features.length > 0) {
      if (!currentMap.getSource('inundation-source')) {
        currentMap.addSource('inundation-source', {
          type: 'geojson',
          data: inundationGeoJSON
        });

        currentMap.addLayer({
          id: 'inundation-fill',
          type: 'fill',
          source: 'inundation-source',
          layout: { visibility: layerVisibility.inundation ? 'visible' : 'none' },
          paint: {
            'fill-color': '#DC2626',
            'fill-opacity': 0.65
          }
        });

        currentMap.addLayer({
          id: 'inundation-outline',
          type: 'line',
          source: 'inundation-source',
          layout: { visibility: layerVisibility.inundation ? 'visible' : 'none' },
          paint: {
            'line-color': '#991B1B',
            'line-width': 2
          }
        });
      } else {
        (currentMap.getSource('inundation-source') as maplibregl.GeoJSONSource).setData(inundationGeoJSON);
      }
    }
  }, [catchmentData, streamsData, locationsData, inundationGeoJSON, layerVisibility, isThreatActive]);

  // Initialize Map
  useEffect(() => {
    if (map.current || !mapContainer.current) return;

    const newMap = new maplibregl.Map({
      container: mapContainer.current,
      style: BASEMAP_STYLES[activeBasemap],
      center: CHUNGTHANG_CENTER,
      zoom: 11.5
    });

    // Add UI Controls
    newMap.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'bottom-right');
    newMap.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-left');

    newMap.on('load', () => {
      map.current = newMap;
      setMapLoaded(true);
      addGeospatialLayers(newMap);
    });

    // Popups for locations
    newMap.on('click', 'locations-points', (e) => {
      if (!e.features || !e.features[0]) return;
      const feat = e.features[0];
      const props = feat.properties as any;
      const geom = feat.geometry as any;
      const coords = geom.coordinates;

      const html = `
        <div style="font-family: Inter, sans-serif; padding: 4px; min-width: 220px;">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px;">
            <strong style="color: #0F172A; font-size: 0.95rem;">${props.name}</strong>
            <span style="background: ${props.color || '#3B82F6'}; color: #FFF; font-size: 0.65rem; font-weight: 700; padding: 2px 6px; border-radius: 4px;">
              ${props.badge || props.category}
            </span>
          </div>
          <div style="color: #475569; font-size: 0.75rem; margin-bottom: 6px;">
            <strong>Type:</strong> ${props.category_label || props.category}<br/>
            <strong>Coordinates:</strong> ${Number(coords[1]).toFixed(4)}°N, ${Number(coords[0]).toFixed(4)}°E<br/>
            <strong>Elevation:</strong> ${props.elevation_m || '--'} m ASL
            ${props.catchment_area_km2 ? `<br/><strong>Catchment:</strong> ${props.catchment_area_km2} km²` : ''}
            ${props.flow_accumulation_cells ? `<br/><strong>Flow Accumulation:</strong> ${Number(props.flow_accumulation_cells).toLocaleString()} cells` : ''}
          </div>
          <p style="color: #334155; font-size: 0.75rem; margin: 0; line-height: 1.35; border-top: 1px solid #E2E8F0; padding-top: 4px;">
            ${props.description || 'Verified corridor waypoint.'}
          </p>
        </div>
      `;

      if (popupRef.current) popupRef.current.remove();
      popupRef.current = new maplibregl.Popup({ closeButton: true, maxWidth: '300px' })
        .setLngLat(coords)
        .setHTML(html)
        .addTo(newMap);
    });

    newMap.on('mouseenter', 'locations-points', () => {
      newMap.getCanvas().style.cursor = 'pointer';
    });
    newMap.on('mouseleave', 'locations-points', () => {
      newMap.getCanvas().style.cursor = '';
    });

    // Popups for Catchment boundary
    newMap.on('click', 'catchment-fill', (e) => {
      if (!e.features || !e.features[0]) return;
      const html = `
        <div style="font-family: Inter, sans-serif; padding: 4px;">
          <strong style="color: #0F172A; font-size: 0.9rem;">Chungthang Basin Catchment</strong>
          <div style="color: #475569; font-size: 0.75rem; margin-top: 4px;">
            <strong>Total Area:</strong> ~2,969.41 km²<br/>
            <strong>Mean Slope:</strong> 27.55°<br/>
            <strong>Mean Elevation:</strong> 4,546 m ASL<br/>
            <strong>Hydrological Unit:</strong> Upper Teesta River System
          </div>
        </div>
      `;
      if (popupRef.current) popupRef.current.remove();
      popupRef.current = new maplibregl.Popup({ closeButton: true })
        .setLngLat(e.lngLat)
        .setHTML(html)
        .addTo(newMap);
    });

    // ResizeObserver for resilient auto-resizing when sidebar collapses/expands
    let resizeObserver: ResizeObserver | null = null;
    if (typeof window !== 'undefined' && 'ResizeObserver' in window && mapContainer.current) {
      resizeObserver = new ResizeObserver(() => {
        if (map.current) {
          map.current.resize();
        }
      });
      resizeObserver.observe(mapContainer.current);
    }

    return () => {
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      if (popupRef.current) popupRef.current.remove();
      newMap.remove();
      map.current = null;
    };
  }, []);

  // Handle Basemap Switch
  const handleBasemapChange = (styleKey: BasemapType) => {
    if (!map.current || styleKey === activeBasemap) return;
    setActiveBasemap(styleKey);

    map.current.setStyle(BASEMAP_STYLES[styleKey]);
    map.current.once('style.load', () => {
      if (map.current) {
        addGeospatialLayers(map.current);
      }
    });
  };

  // Re-add or update layers when dependencies change
  useEffect(() => {
    if (!map.current || !mapLoaded) return;
    addGeospatialLayers(map.current);

    // Update river styling on hazard state change
    if (map.current.getLayer('streams-layer')) {
      map.current.setPaintProperty('streams-layer', 'line-color', isThreatActive ? '#EF4444' : '#38BDF8');
      map.current.setPaintProperty('streams-layer', 'line-width', isThreatActive ? 3.2 : 2.0);
    }
  }, [mapLoaded, catchmentData, streamsData, locationsData, inundationGeoJSON, isThreatActive, addGeospatialLayers]);

  // Handle Layer Visibility Toggles
  const toggleLayer = (layerKey: keyof typeof layerVisibility) => {
    const updated = !layerVisibility[layerKey];
    setLayerVisibility(prev => ({ ...prev, [layerKey]: updated }));

    if (!map.current) return;
    const vis = updated ? 'visible' : 'none';

    if (layerKey === 'catchment') {
      if (map.current.getLayer('catchment-fill')) map.current.setLayoutProperty('catchment-fill', 'visibility', vis);
      if (map.current.getLayer('catchment-line')) map.current.setLayoutProperty('catchment-line', 'visibility', vis);
    } else if (layerKey === 'streams') {
      if (map.current.getLayer('streams-layer')) map.current.setLayoutProperty('streams-layer', 'visibility', vis);
    } else if (layerKey === 'locations') {
      if (map.current.getLayer('locations-points')) map.current.setLayoutProperty('locations-points', 'visibility', vis);
      if (map.current.getLayer('locations-halo')) map.current.setLayoutProperty('locations-halo', 'visibility', vis);
      if (map.current.getLayer('locations-labels')) map.current.setLayoutProperty('locations-labels', 'visibility', vis);
    } else if (layerKey === 'inundation') {
      if (map.current.getLayer('inundation-fill')) map.current.setLayoutProperty('inundation-fill', 'visibility', vis);
      if (map.current.getLayer('inundation-outline')) map.current.setLayoutProperty('inundation-outline', 'visibility', vis);
    }
  };

  // View bounds functions
  const focusCorridor = () => {
    if (!map.current) return;
    map.current.flyTo({ center: CHUNGTHANG_CENTER, zoom: 12, speed: 1.2 });
  };

  const focusFullCatchment = () => {
    if (!map.current) return;
    map.current.fitBounds(CATCHMENT_BOUNDS, { padding: 40, maxZoom: 11 });
  };

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      {/* Map Container */}
      <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />

      {/* 1. TOP-LEFT: Data Status Indicator HUD */}
      <div style={{
        position: 'absolute',
        top: '12px',
        left: '12px',
        zIndex: 20,
        background: 'rgba(15, 23, 42, 0.90)',
        backdropFilter: 'blur(8px)',
        border: '1px solid #334155',
        borderRadius: '8px',
        padding: '10px 14px',
        boxShadow: '0 4px 14px rgba(0,0,0,0.4)',
        maxWidth: '380px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: isThreatActive ? '#EF4444' : (hudStatus === 'STALE' ? '#F59E0B' : '#10B981')
            }} className={isThreatActive ? 'animate-pulse' : ''} />
            <strong style={{ fontSize: '0.85rem', color: '#F8FAFC', letterSpacing: '0.2px' }}>
              CHUNGTHANG CORRIDOR
            </strong>
          </div>
          <span style={{
            fontSize: '0.65rem',
            fontWeight: 700,
            padding: '2px 6px',
            borderRadius: '4px',
            background: hudStatus === 'FORECAST' ? '#0369A1' : (hudStatus === 'LIVE' ? '#059669' : (hudStatus === 'SIMULATION' ? '#D97706' : '#DC2626')),
            color: '#FFFFFF'
          }}>
            {hudStatus}
          </span>
        </div>

        <div style={{ fontSize: '0.75rem', color: '#94A3B8', display: 'flex', flexDirection: 'column', gap: '3px' }}>
          <div>
            <strong>Source:</strong> <span style={{ color: '#E2E8F0' }}>{hudSource}</span>
          </div>
          {validTimeStr && (
            <div>
              <strong>Valid/Horizon:</strong> <span style={{ color: '#E2E8F0' }}>{validTimeStr}</span>
            </div>
          )}
          {retrievalTimeStr && (
            <div>
              <strong>Last Sync:</strong> <span style={{ color: '#E2E8F0' }}>{retrievalTimeStr}</span>
            </div>
          )}
          {activeAlert && (
            <div style={{ marginTop: '4px', paddingTop: '4px', borderTop: '1px solid #334155', color: isThreatActive ? '#FCA5A5' : '#86EFAC' }}>
              <strong>Active Alert:</strong> {activeAlert.headline}
            </div>
          )}
        </div>

        {/* Inundation limitation notice */}
        {(!inundationGeoJSON || !inundationGeoJSON.features || inundationGeoJSON.features.length === 0) && (
          <div style={{
            marginTop: '6px',
            paddingTop: '6px',
            borderTop: '1px solid #334155',
            fontSize: '0.7rem',
            color: '#CBD5E1',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '4px'
          }}>
            <Info size={13} style={{ flexShrink: 0, marginTop: '1px', color: '#38BDF8' }} />
            <span>Showing verified 30m stream corridor. 2D hydrodynamic inundation depth requires calibrated channel bathymetry.</span>
          </div>
        )}
      </div>

      {/* 2. TOP-RIGHT: Basemap Selector & View Extents */}
      <div style={{
        position: 'absolute',
        top: '12px',
        right: '12px',
        zIndex: 20,
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        alignItems: 'flex-end'
      }}>
        {/* Basemap switcher */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.90)',
          backdropFilter: 'blur(8px)',
          border: '1px solid #334155',
          borderRadius: '8px',
          padding: '4px',
          display: 'flex',
          gap: '4px'
        }}>
          <button
            onClick={() => handleBasemapChange('dark')}
            style={{
              background: activeBasemap === 'dark' ? '#1E293B' : 'transparent',
              color: activeBasemap === 'dark' ? '#38BDF8' : '#94A3B8',
              border: 'none',
              borderRadius: '4px',
              padding: '4px 8px',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            🌙 Dark
          </button>
          <button
            onClick={() => handleBasemapChange('topo')}
            style={{
              background: activeBasemap === 'topo' ? '#1E293B' : 'transparent',
              color: activeBasemap === 'topo' ? '#38BDF8' : '#94A3B8',
              border: 'none',
              borderRadius: '4px',
              padding: '4px 8px',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            ⛰️ Topo
          </button>
          <button
            onClick={() => handleBasemapChange('satellite')}
            style={{
              background: activeBasemap === 'satellite' ? '#1E293B' : 'transparent',
              color: activeBasemap === 'satellite' ? '#38BDF8' : '#94A3B8',
              border: 'none',
              borderRadius: '4px',
              padding: '4px 8px',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            🛰️ Satellite
          </button>
        </div>

        {/* Extent shortcuts */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.90)',
          backdropFilter: 'blur(8px)',
          border: '1px solid #334155',
          borderRadius: '8px',
          padding: '4px',
          display: 'flex',
          gap: '4px'
        }}>
          <button
            onClick={focusCorridor}
            title="Focus Chungthang Corridor (Zoom 12)"
            style={{
              background: 'transparent',
              color: '#F8FAFC',
              border: 'none',
              borderRadius: '4px',
              padding: '4px 8px',
              fontSize: '0.75rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <Minimize2 size={12} /> Corridor
          </button>
          <button
            onClick={focusFullCatchment}
            title="Fit Full Watershed Catchment (~2,969 km²)"
            style={{
              background: 'transparent',
              color: '#F8FAFC',
              border: 'none',
              borderRadius: '4px',
              padding: '4px 8px',
              fontSize: '0.75rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <Maximize2 size={12} /> Basin
          </button>
        </div>
      </div>

      {/* 3. BOTTOM-RIGHT: Layer Controls & Toggle Panel */}
      <div style={{
        position: 'absolute',
        bottom: '80px',
        right: '12px',
        zIndex: 20,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: '6px'
      }}>
        {showControls && (
          <div style={{
            background: 'rgba(15, 23, 42, 0.92)',
            backdropFilter: 'blur(8px)',
            border: '1px solid #334155',
            borderRadius: '8px',
            padding: '12px 14px',
            minWidth: '220px',
            boxShadow: '0 6px 18px rgba(0,0,0,0.5)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px'
          }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#F8FAFC', borderBottom: '1px solid #334155', paddingBottom: '6px' }}>
              Map Layers
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.75rem', color: '#E2E8F0', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={layerVisibility.catchment}
                onChange={() => toggleLayer('catchment')}
              />
              Watershed (~2,969 km²)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.75rem', color: '#E2E8F0', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={layerVisibility.streams}
                onChange={() => toggleLayer('streams')}
              />
              River Network (1,413 streams)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.75rem', color: '#E2E8F0', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={layerVisibility.locations}
                onChange={() => toggleLayer('locations')}
              />
              Settlements & Gauges
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.75rem', color: '#E2E8F0', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={layerVisibility.inundation}
                onChange={() => toggleLayer('inundation')}
              />
              2D Flood Inundation
            </label>
          </div>
        )}

        <button
          onClick={() => setShowControls(!showControls)}
          style={{
            background: 'rgba(15, 23, 42, 0.90)',
            border: '1px solid #334155',
            borderRadius: '6px',
            color: '#38BDF8',
            padding: '6px 10px',
            fontSize: '0.75rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          <Layers size={14} /> Layers
        </button>
      </div>

      {/* 4. BOTTOM-CENTER: Collapsible Map Legend with CWC vs DEM Clarification */}
      <div style={{
        position: 'absolute',
        bottom: '12px',
        left: '120px',
        zIndex: 20,
        background: 'rgba(15, 23, 42, 0.90)',
        backdropFilter: 'blur(8px)',
        border: '1px solid #334155',
        borderRadius: '8px',
        padding: '6px 12px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
        maxWidth: 'calc(100% - 240px)'
      }}>
        {showLegend ? (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '4px' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#F8FAFC' }}>
                Legend & Symbology
              </span>
              <button
                onClick={() => setShowLegend(false)}
                style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer', padding: 0 }}
              >
                <EyeOff size={12} />
              </button>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', fontSize: '0.7rem', color: '#CBD5E1' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ display: 'inline-block', width: '12px', height: '3px', background: isThreatActive ? '#EF4444' : '#38BDF8' }} />
                <span>Teesta Streams ({isThreatActive ? 'Threat Tier' : 'Normal'})</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#F59E0B', border: '1px solid #FFF' }} />
                <span>CWC Reference Gauge (27.5833°N, 88.6475°E)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#10B981', border: '1px solid #FFF' }} />
                <span>DEM-Snapped Outlet (27.5851°N, 88.6551°E)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ display: 'inline-block', width: '8px', height: '8px', background: '#EF4444', borderRadius: '2px' }} />
                <span>Teesta III Dam Site</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ display: 'inline-block', width: '12px', height: '2px', borderTop: '2px dashed #0284C7' }} />
                <span>Catchment Divide (~2,969 km²)</span>
              </div>
              {terrainMeta && (
                <div style={{ width: '100%', fontSize: '0.65rem', color: '#94A3B8', marginTop: '4px', borderTop: '1px solid #334155', paddingTop: '3px' }}>
                  SRTM 30m Grid • DEM Snap Offset: {terrainMeta.outlet_snap_distance_deg}° (~870m) • Accumulation: {terrainMeta.outlet_accumulation_cells?.toLocaleString()} cells
                </div>
              )}
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowLegend(true)}
            style={{ background: 'none', border: 'none', color: '#94A3B8', fontSize: '0.7rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', padding: 0 }}
          >
            <Eye size={12} /> Show Legend
          </button>
        )}
      </div>
    </div>
  );
};

export default FloodMap;
