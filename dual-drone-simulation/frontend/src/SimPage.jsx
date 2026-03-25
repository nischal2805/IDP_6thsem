import { useState, useCallback } from 'react';
import { useSimSocket } from './useSimSocket';
import DroneCameraView from './DroneCameraView';
import DronePanel from './DronePanel';
import OccupancyChart from './OccupancyChart';
import CrushRiskGauge from './CrushRiskGauge';
import ControlPanel from './ControlPanel';
import ReplayControls from './ReplayControls';

export default function SimPage() {
  const {
    connected,
    simState,
    historyExport,
    startSimulation,
    stopSimulation,
    resetSimulation,
    pauseSimulation,
    resumeSimulation,
    injectPanic,
    startEvacuation,
    setCapacity,
    setSpawnRate,
    requestHistoryExport,
  } = useSimSocket();

  const [isPaused, setIsPaused] = useState(false);
  const [panicMode, setPanicMode] = useState(false);

  // Track running state from simState.tick instead of just local state
  const isRunning = simState && simState.tick > 0;
  const isSimActive = isRunning && !isPaused;

  const handleStart = (scenario, capacity, initialIndoor, initialOutdoor) => {
    setIsPaused(false);
    startSimulation(scenario, capacity, initialIndoor, initialOutdoor);
  };

  const handlePause = () => {
    setIsPaused(true);
    pauseSimulation();
  };

  const handleResume = () => {
    setIsPaused(false);
    resumeSimulation();
  };

  const handleStop = () => {
    setIsPaused(false);
    stopSimulation();
  };

  const handleCanvasClick = useCallback((x, y) => {
    if (panicMode && isSimActive) {
      injectPanic(x, y);
      setPanicMode(false);
    }
  }, [panicMode, isSimActive, injectPanic]);

  const handleInjectPanic = () => {
    setPanicMode(true);
  };

  const handleExport = () => {
    requestHistoryExport();
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'GREEN': return 'text-emerald-400';
      case 'YELLOW': return 'text-yellow-400';
      case 'ORANGE': return 'text-orange-400';
      case 'RED': return 'text-red-400';
      case 'CRITICAL': return 'text-red-500 animate-pulse';
      case 'EVACUATING': return 'text-blue-400';
      case 'STAGED': return 'text-blue-300';
      case 'CLEAR': return 'text-emerald-400';
      default: return 'text-gray-400';
    }
  };

  return (
    <div className="min-h-screen bg-sim-darker p-4">
      {/* Header */}
      <header className="mb-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <span className="text-3xl">🛸</span>
              Dual Drone Surveillance System
            </h1>
            <p className="text-gray-400 text-sm">Real-time aerial crowd monitoring • PySocialForce physics engine</p>
          </div>
          <div className="flex items-center gap-4">
            {/* System Status */}
            {simState && (
              <div className={`px-4 py-2 rounded-lg border-2 ${getStatusColor(simState.status)} font-mono`}>
                <span className="font-bold text-sm">{simState.status}</span>
              </div>
            )}
            {/* Connection Status */}
            <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border-2 ${
              connected ? 'bg-emerald-950/50 border-emerald-600' : 'bg-red-950/50 border-red-600'
            }`}>
              <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
              <span className="text-sm font-mono font-bold">
                {connected ? 'CONNECTED' : 'OFFLINE'}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left Column - Drone Camera Feeds */}
        <div className="col-span-8 space-y-4">
          {/* Panic Mode Indicator */}
          {panicMode && (
            <div className="px-4 py-2 bg-orange-600 text-white text-sm font-bold rounded-lg border-2 border-orange-400 animate-pulse">
              ⚠️ PANIC INJECTION MODE - Click on any camera feed to inject panic at location
            </div>
          )}

          {/* Dual Camera Feed Grid */}
          <div className="grid grid-cols-1 gap-4">
            {/* Drone A - Indoor Camera */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 px-3 py-1 bg-blue-900/30 border border-blue-700 rounded">
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                <span className="text-sm font-mono text-blue-300">DRONE A - INDOOR MONITORING</span>
              </div>
              <DroneCameraView 
                simState={simState} 
                onCanvasClick={handleCanvasClick}
                droneId="A"
              />
            </div>

            {/* Drone B - Outdoor Camera */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 px-3 py-1 bg-emerald-900/30 border border-emerald-700 rounded">
                <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
                <span className="text-sm font-mono text-emerald-300">DRONE B - QUEUE MANAGEMENT</span>
              </div>
              <DroneCameraView 
                simState={simState} 
                onCanvasClick={handleCanvasClick}
                droneId="B"
              />
            </div>
          </div>

          {/* Analytics Row */}
          <div className="grid grid-cols-2 gap-4">
            <OccupancyChart 
              history={simState?.history} 
              capacity={simState?.capacity || 100}
            />
            <CrushRiskGauge 
              crushRisk={simState?.crush_risk_index || 0}
              warning={simState?.crush_warning}
              critical={simState?.crush_critical}
              scenarioType={simState?.scenario_type}
            />
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-5 gap-3">
            <StatCard label="Simulation Tick" value={simState?.tick || 0} />
            <StatCard label="Indoor Count" value={simState?.indoor_count || 0} />
            <StatCard label="Queue Size" value={simState?.outdoor_count || 0} />
            <StatCard label="Scenario" value={simState?.scenario || '-'} />
            <StatCard 
              label="Gate Status" 
              value={simState?.gate || 'OPEN'} 
              color={
                simState?.gate === 'OPEN' ? 'text-emerald-400' :
                simState?.gate === 'THROTTLE' ? 'text-yellow-400' : 'text-red-400'
              }
            />
          </div>
        </div>

        {/* Right Column - Control Panels */}
        <div className="col-span-4 space-y-4">
          {/* Drone Status Panels */}
          <DronePanel 
            droneData={simState?.drone_a} 
            status={simState?.status || 'GREEN'}
          />
          <DronePanel 
            droneData={simState?.drone_b} 
            status={simState?.status || 'GREEN'}
          />

          {/* Control Panel */}
          <ControlPanel
            onStart={handleStart}
            onStop={handleStop}
            onPause={handlePause}
            onResume={handleResume}
            onReset={resetSimulation}
            onInjectPanic={handleInjectPanic}
            onStartEvacuation={startEvacuation}
            onCapacityChange={setCapacity}
            onSpawnRateChange={setSpawnRate}
            isRunning={isRunning}
            isPaused={isPaused}
            simState={simState}
          />

          {/* Replay Controls */}
          <ReplayControls 
            history={historyExport || simState?.history}
            onExport={handleExport}
          />
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-4 text-center text-xs text-gray-600 font-mono">
        <p>IDP PROJECT • AERIAL CROWD SURVEILLANCE • EXTENDED SOCIAL FORCE MODEL (PySocialForce)</p>
      </footer>
    </div>
  );
}

function StatCard({ label, value, color = 'text-white' }) {
  return (
    <div className="bg-sim-card rounded-lg p-3 border border-sim-border">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`text-xl font-bold font-mono ${color}`}>{value}</div>
    </div>
  );
}
