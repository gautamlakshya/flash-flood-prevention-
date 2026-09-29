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

  // Fetch map config from backend
  useEffect(() => {
    fetch(`${(import.meta as any).env.VITE_API_URL || 'http://localhost:8000'}/api/v1/simulation/map-config`)
      .then(res => res.json())
      .then(data => {
        if (data.status === 'CONFIGURED') {
          setMapConfig(data);
        }
      })
      .catch(e => console.error("Failed to fetch map config", e));
  }, []);

  useEffect(() => {
    if (!mapConfig || map.current) return;
    
    if (mapContainer.current) {
      map.current = new maplibregl.Map({
        container: mapContainer.current,
        style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
        center: mapConfig.default_center,
        zoom: mapConfig.default_zoom
      });

      map.current.on('load', () => {
        // Only add mock river in SIMULATION mode
        if (dataMode === 'SIMULATION') {
            map.current?.addSource('rivers', {
              type: 'geojson',
              data: {
                type: 'FeatureCollection',
                features: [
                  {
                    type: 'Feature',
                    properties: { id: 'CHUNGTHANG_SIM', capacity: '1000' },
                    geometry: {
                      type: 'LineString',
                      coordinates: [
                        [88.6475, 27.65],
                        [88.6475, 27.6033],
                        [88.6475, 27.55]
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
                'line-color': '#3B82F6',
                'line-width': 3
              }
            });
        }
      });
    }

    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, [mapConfig, dataMode]);

  useEffect(() => {
    if (!map.current || !map.current.isStyleLoaded()) return;

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
            'fill-opacity': 0.4
          }
        });
      } else {
        (map.current.getSource('inundation') as maplibregl.GeoJSONSource).setData(inundationGeoJSON);
      }
    } else {
      if (map.current.getLayer('inundation-layer')) {
        map.current.removeLayer('inundation-layer');
        map.current.removeSource('inundation');
      }
    }

    if (dataMode === 'SIMULATION' && map.current.getLayer('rivers-layer')) {
        if (isWarning) {
          map.current.setPaintProperty('rivers-layer', 'line-color', '#EF4444');
          map.current.setPaintProperty('rivers-layer', 'line-width', 5);
        } else {
          map.current.setPaintProperty('rivers-layer', 'line-color', '#3B82F6');
          map.current.setPaintProperty('rivers-layer', 'line-width', 3);
        }
    }
  }, [isWarning, inundationGeoJSON, dataMode]);

  return (
    <div ref={mapContainer} style={{ width: '100%', height: '100%' }}>
      {!mapConfig && <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', color: 'white' }}>Loading map configuration...</div>}
    </div>
  );
};

export default FloodMap;
