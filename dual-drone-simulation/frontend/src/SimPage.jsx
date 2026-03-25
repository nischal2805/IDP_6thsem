import { useState, useCallback } from 'react';
import { useSimSocket } from './useSimSocket';
import FloorCanvas from './FloorCanvas';
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

  const isRunning = simState?.tick > 0 && !isPaused;

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
    if (panicMode && isRunning) {
      injectPanic(x, y);
      setPanicMode(false);
    }
  }, [panicMode, isRunning, injectPanic]);

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
      <header className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Dual Drone Crowd Simulation</h1>
            <p className="text-gray-400 text-sm">Real-time crowd flow monitoring with PySocialForce physics</p>
          </div>
          <div className="flex items-center gap-4">
            {/* Connection Status */}
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-red-500'}`} />
              <span className="text-sm text-gray-400">
                {connected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
            {/* System Status */}
            {simState && (
              <div className={`px-3 py-1 rounded-full border ${getStatusColor(simState.status)}`}>
                <span className="font-bold">{simState.status}</span>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left Column - Visualization */}
        <div className="col-span-8 space-y-4">
          {/* Canvas with panic mode indicator */}
          <div className="relative">
            {panicMode && (
              <div className="absolute top-2 left-2 z-10 px-3 py-1 bg-orange-600 text-white text-sm font-bold rounded">
                Click on canvas to inject panic
              </div>
            )}
            <FloorCanvas 
              simState={simState} 
              onCanvasClick={handleCanvasClick}
            />
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-2 gap-4">
            <OccupancyChart 
              history={simState?.history} 
              capacity={simState?.capacity || 100}
            />
            <CrushRiskGauge 
              crushRisk={simState?.crush_risk_index || 0}
              warning={simState?.crush_warning}
              critical={simState?.crush_critical}
            />
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-5 gap-4">
            <StatCard label="Tick" value={simState?.tick || 0} />
            <StatCard label="Indoor" value={simState?.indoor_count || 0} />
            <StatCard label="Outdoor" value={simState?.outdoor_count || 0} />
            <StatCard label="Scenario" value={simState?.scenario || '-'} />
            <StatCard 
              label="Gate" 
              value={simState?.gate || 'OPEN'} 
              color={
                simState?.gate === 'OPEN' ? 'text-emerald-400' :
                simState?.gate === 'THROTTLE' ? 'text-yellow-400' : 'text-red-400'
              }
            />
          </div>
        </div>

        {/* Right Column - Panels */}
        <div className="col-span-4 space-y-4">
          {/* Drone Panels */}
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
            onInjectPanic={handleInjectPanic}
            onStartEvacuation={startEvacuation}
            onCapacityChange={setCapacity}
            onSpawnRateChange={setSpawnRate}
            isRunning={!!simState?.tick}
            isPaused={isPaused}
          />

          {/* Replay Controls */}
          <ReplayControls 
            history={historyExport || simState?.history}
            onExport={handleExport}
          />
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-6 text-center text-sm text-gray-500">
        <p>IDP — Crowd Simulation Module | Physics: PySocialForce (Extended Social Force Model)</p>
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
