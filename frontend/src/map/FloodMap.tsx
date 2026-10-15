import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useAppStore } from '../stores/appStore';

interface FloodMapProps {
  isWarning: boolean;
  inundationGeoJSON?: any;
}

const FloodMap: React.FC<FloodMapProps> = ({ isWarning, inundationGeoJSON }) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const { dataMode } = useAppStore();
  const [mapConfig, setMapConfig] = useState<any>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  // Fetch map config from backend with immediate fallback
  useEffect(() => {
    let isMounted = true;
    const apiUrl = ((import.meta as any).env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

    fetch(`${apiUrl}/api/v1/simulation/map-config`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        if (!isMounted) return;
        if (data.status === 'CONFIGURED' || data.status === 'READY') {
          setMapConfig(data);
        } else {
          setMapConfig({
            status: 'CONFIGURED',
            study_area: data.study_area || 'Chungthang',
            default_center: data.default_center || [88.6475, 27.6033],
            default_zoom: data.default_zoom || 11
          });
        }
      })
      .catch(e => {
        if (!isMounted) return;
        console.warn("Failed to fetch map config, utilizing Chungthang fallback coordinates:", e);
        // Fallback ensures Command Center NEVER stays stuck in loading
        setMapConfig({
          status: 'FALLBACK',
          study_area: 'Chungthang Basin',
          default_center: [88.6475, 27.6033],
          default_zoom: 11
        });
      });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!mapConfig || map.current || !mapContainer.current) return;

    const centerCoords = (mapConfig.default_center && mapConfig.default_center.length === 2)
      ? mapConfig.default_center
      : [88.6475, 27.6033];

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: centerCoords,
      zoom: mapConfig.default_zoom || 11
    });

    map.current.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'bottom-right');

    map.current.on('load', () => {
      setMapLoaded(true);

      // Add Teesta river confluence & mainstem network
      map.current?.addSource('rivers', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [
            {
              type: 'Feature',
              properties: { id: 'LACHEN_CHU', name: 'Lachen Chu' },
              geometry: {
                type: 'LineString',
                coordinates: [
                  [88.58, 27.70],
                  [88.61, 27.65],
                  [88.6475, 27.6033]
                ]
              }
            },
            {
              type: 'Feature',
              properties: { id: 'LACHUNG_CHU', name: 'Lachung Chu' },
              geometry: {
                type: 'LineString',
                coordinates: [
                  [88.74, 27.68],
                  [88.70, 27.64],
                  [88.6475, 27.6033]
                ]
              }
            },
            {
              type: 'Feature',
              properties: { id: 'TEESTA_MAIN', name: 'Teesta River Mainstem', capacity: 1000 },
              geometry: {
                type: 'LineString',
                coordinates: [
                  [88.6475, 27.6033],
                  [88.6551, 27.5851],
                  [88.6500, 27.5400],
                  [88.6300, 27.4800]
                ]
              }
            }
          ]
        }
      });

      map.current?.addLayer({
        id: 'rivers-layer',
        type: 'line',
        source: 'rivers',
        layout: {
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': isWarning ? '#EF4444' : '#38BDF8',
          'line-width': 3.5,
          'line-opacity': 0.85
        }
      });

      // Add CWC Station Target Outlet Marker
      map.current?.addSource('cwc-outlet', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [
            {
              type: 'Feature',
              properties: { name: 'CWC Chungthang Station' },
              geometry: {
                type: 'Point',
                coordinates: [88.6551, 27.5851]
              }
            }
          ]
        }
      });

      map.current?.addLayer({
        id: 'cwc-outlet-point',
        type: 'circle',
        source: 'cwc-outlet',
        paint: {
          'circle-radius': 7,
          'circle-color': '#F59E0B',
          'circle-stroke-width': 2,
          'circle-stroke-color': '#FFFFFF'
        }
      });
    });

    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, [mapConfig]);

  // Handle inundation GeoJSON updates
  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    if (inundationGeoJSON && inundationGeoJSON.features && inundationGeoJSON.features.length > 0) {
      if (!map.current.getSource('inundation')) {
        map.current.addSource('inundation', {
          type: 'geojson',
          data: inundationGeoJSON
        });

        map.current.addLayer({
          id: 'inundation-layer',
          type: 'fill',
          source: 'inundation',
          paint: {
            'fill-color': '#EF4444',
            'fill-opacity': 0.55
          }
        });

        map.current.addLayer({
          id: 'inundation-outline',
          type: 'line',
          source: 'inundation',
          paint: {
            'line-color': '#DC2626',
            'line-width': 2
          }
        });
      } else {
        (map.current.getSource('inundation') as maplibregl.GeoJSONSource).setData(inundationGeoJSON);
      }
    } else {
      if (map.current.getLayer('inundation-outline')) map.current.removeLayer('inundation-outline');
      if (map.current.getLayer('inundation-layer')) map.current.removeLayer('inundation-layer');
      if (map.current.getSource('inundation')) map.current.removeSource('inundation');
    }

    if (map.current.getLayer('rivers-layer')) {
      map.current.setPaintProperty('rivers-layer', 'line-color', isWarning ? '#EF4444' : '#38BDF8');
      map.current.setPaintProperty('rivers-layer', 'line-width', isWarning ? 5 : 3.5);
    }
  }, [isWarning, inundationGeoJSON, mapLoaded, dataMode]);

  return (
    <div ref={mapContainer} style={{ width: '100%', height: '100%', position: 'relative' }}>
      {!mapConfig && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          color: '#E2E8F0',
          background: 'rgba(15, 23, 42, 0.85)',
          padding: '12px 24px',
          borderRadius: '8px',
          border: '1px solid #334155',
          fontSize: '0.9rem',
          zIndex: 20
        }}>
          Initializing Chungthang Terrain Basemap...
        </div>
      )}
      {mapConfig && (
        <div style={{
          position: 'absolute',
          bottom: '12px',
          left: '12px',
          zIndex: 10,
          background: 'rgba(15, 23, 42, 0.85)',
          padding: '6px 12px',
          borderRadius: '6px',
          border: '1px solid var(--border-color)',
          fontSize: '0.75rem',
          color: 'var(--text-muted)'
        }}>
          Study Area: <strong>{mapConfig.study_area || 'Chungthang'}</strong> | Target: <strong>CWC Station (27.585°N, 88.655°E)</strong>
        </div>
      )}
    </div>
  );
};

export default FloodMap;
