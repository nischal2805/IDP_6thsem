import { useState, useEffect, useCallback } from 'react';
import DensityChart from './components/DensityChart';
import ForecastPanel from './components/ForecastPanel';
import AlertFeed from './components/AlertFeed';
import StatusBar from './components/StatusBar';
import HeatmapView from './components/HeatmapView';
import DroneStatus from './components/DroneStatus';

const WS_URL = 'ws://localhost:8080/ws/dashboard';

export default function App() {
  const [connected, setConnected] = useState(false);
  const [jetsonConnected, setJetsonConnected] = useState(false);
  const [inferenceData, setInferenceData] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [history, setHistory] = useState([]);

  // WebSocket connection
  useEffect(() => {
    let ws = null;
    let reconnectTimeout = null;

    const connect = () => {
      ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        setConnected(true);
        console.log('Connected to ground server');
      };

      ws.onclose = () => {
        setConnected(false);
        console.log('Disconnected from ground server');
        reconnectTimeout = setTimeout(connect, 3000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleMessage(message);
      };
    };

    connect();

    return () => {
      if (ws) ws.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, []);

  const handleMessage = useCallback((message) => {
    switch (message.type) {
      case 'initial_state':
        setJetsonConnected(message.connected_jetson);
        if (message.last_data) setInferenceData(message.last_data);
        if (message.forecast) setForecast(message.forecast);
        if (message.active_alerts) setAlerts(message.active_alerts);
        break;

      case 'inference_update':
        setJetsonConnected(true);
        setInferenceData(message.data);
        if (message.forecast) setForecast(message.forecast);
        
        // Update history
        setHistory(prev => {
          const newPoint = {
            time: Date.now(),
            count: message.data?.density?.count || 0,
            persons: message.data?.person_count || 0
          };
          const updated = [...prev, newPoint].slice(-100);
          return updated;
        });

        // Handle new alerts
        if (message.data?.alerts?.length > 0) {
          setAlerts(prev => [...message.data.alerts, ...prev].slice(0, 50));
        }
        break;

      case 'alert_acknowledged':
        setAlerts(prev =>
          prev.map(a =>
            a.alert_id === message.alert_id ? { ...a, acknowledged: true } : a
          )
        );
        break;

      case 'history':
        // Handle history response
        break;

      default:
        console.log('Unknown message type:', message.type);
    }
  }, []);

  const acknowledgeAlert = useCallback((alertId) => {
    // Would send via WebSocket in production
    setAlerts(prev =>
      prev.map(a =>
        a.alert_id === alertId ? { ...a, acknowledged: true } : a
      )
    );
  }, []);

  return (
    <div className="min-h-screen bg-darker p-4">
      {/* Header */}
      <header className="mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <img src="/drone.svg" alt="Drone" className="w-10 h-10" />
            <div>
              <h1 className="text-2xl font-bold text-white">Crowd Monitoring Dashboard</h1>
              <p className="text-gray-400 text-sm">IDP - Drone-Based Real-Time Monitoring</p>
            </div>
          </div>
          <StatusBar
            connected={connected}
            jetsonConnected={jetsonConnected}
            fps={inferenceData?.fps || 0}
            frameId={inferenceData?.frame_id || 0}
          />
        </div>
      </header>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left Column - Main Visualization */}
        <div className="col-span-8 space-y-4">
          {/* Heatmap / Camera View */}
          <div className="card">
            <h2 className="text-lg font-bold mb-3">Live Density Heatmap</h2>
            <HeatmapView
              densityData={inferenceData?.density}
              persons={inferenceData?.persons}
              anomaly={inferenceData?.anomaly}
            />
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-2 gap-4">
            <DensityChart history={history} />
            <ForecastPanel forecast={forecast} />
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-4 gap-4">
            <StatCard
              label="Person Count"
              value={inferenceData?.person_count || 0}
              icon="👥"
            />
            <StatCard
              label="Density Estimate"
              value={Math.round(inferenceData?.density?.count || 0)}
              icon="📊"
            />
            <StatCard
              label="Peak Density"
              value={(inferenceData?.density?.peak_density || 0).toFixed(1)}
              icon="📍"
              warning={inferenceData?.density?.peak_density > 5}
            />
            <StatCard
              label="Anomaly"
              value={inferenceData?.anomaly?.type || 'normal'}
              icon={inferenceData?.anomaly?.detected ? '⚠️' : '✅'}
              warning={inferenceData?.anomaly?.detected}
            />
          </div>
        </div>

        {/* Right Column - Alerts & Status */}
        <div className="col-span-4 space-y-4">
          {/* Alert Feed */}
          <AlertFeed
            alerts={alerts}
            onAcknowledge={acknowledgeAlert}
          />

          {/* Drone Status */}
          <DroneStatus
            gps={inferenceData?.gps}
            timing={inferenceData?.timing_ms}
            falls={inferenceData?.falls}
          />
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-6 text-center text-sm text-gray-500">
        <p>IDP - Drone-Based Crowd Monitoring System | RVCE Drone Club</p>
      </footer>
    </div>
  );
}

function StatCard({ label, value, icon, warning = false }) {
  return (
    <div className={`card ${warning ? 'border-warning' : ''}`}>
      <div className="flex items-center justify-between">
        <span className="text-2xl">{icon}</span>
        {warning && <span className="text-warning text-xs font-bold">!</span>}
      </div>
      <div className="mt-2">
        <div className={`text-2xl font-bold ${warning ? 'text-warning' : 'text-white'}`}>
          {value}
        </div>
        <div className="text-sm text-gray-400">{label}</div>
      </div>
    </div>
  );
}
