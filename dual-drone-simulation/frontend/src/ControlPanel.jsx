import { useState, useEffect } from 'react';

export default function ControlPanel({
  onStart,
  onStop,
  onPause,
  onResume,
  onReset,
  onInjectPanic,
  onStartEvacuation,
  onCapacityChange,
  onSpawnRateChange,
  isRunning,
  isPaused,
  simState,
}) {
  const [scenario, setScenario] = useState(1);
  const [capacity, setCapacity] = useState(100);
  const [initialIndoor, setInitialIndoor] = useState(20);
  const [initialOutdoor, setInitialOutdoor] = useState(10);
  const [spawnRate, setSpawnRate] = useState(2.0);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [showVelocity, setShowVelocity] = useState(true);
  const [scenarios, setScenarios] = useState([]);

  useEffect(() => {
    fetch('http://localhost:8000/api/scenarios')
      .then(response => response.json())
      .then(data => setScenarios(data.scenarios))
      .catch(error => {
        console.error('Failed to fetch scenarios:', error);
        // Fallback to hardcoded scenarios if backend is unavailable
        setScenarios([
          { id: 1, name: "Entry + Exit", icon: "↔️", description: "Basic flow" },
          { id: 2, name: "Entry Only", icon: "➡️", description: "Capacity test" },
          { id: 3, name: "Evacuation", icon: "🚨", description: "Emergency" },
          { id: 4, name: "Stadium Sections", icon: "🏟️", description: "Reserved areas" },
          { id: 5, name: "Multi-Lane", icon: "🚦", description: "Load balancing" },
          { id: 6, name: "Tiered (VIP)", icon: "🎫", description: "Priority lanes" },
          { id: 7, name: "Bidirectional", icon: "⇄", description: "Counter-flow" },
          { id: 8, name: "Predictive", icon: "🔮", description: "AI control" },
        ]);
      });
  }, []);

  const handleStart = () => {
    onStart(scenario, capacity, initialIndoor, initialOutdoor);
  };

  const handleCapacityChange = (e) => {
    const val = parseInt(e.target.value);
    setCapacity(val);
    if (isRunning) {
      onCapacityChange(val);
    }
  };

  const handleSpawnRateChange = (e) => {
    const val = parseFloat(e.target.value);
    setSpawnRate(val);
    if (isRunning) {
      onSpawnRateChange(val);
    }
  };

  return (
    <div className="bg-sim-card rounded-lg p-4 border border-sim-border space-y-4">
      <h3 className="font-bold text-lg text-white mb-3">Simulation Control</h3>

      {/* Scenario Grid */}
      <div>
        <label className="block text-sm text-gray-400 mb-2 font-medium">Scenario Selection</label>
        <div className="grid grid-cols-2 gap-2">
          {scenarios.map((s) => (
            <button
              key={s.id}
              onClick={() => setScenario(s.id)}
              disabled={isRunning}
              className={`px-2 py-2 rounded text-xs font-medium transition-all ${
                scenario === s.id
                  ? 'bg-blue-600 text-white shadow-lg'
                  : 'bg-sim-darker text-gray-300 hover:bg-sim-border'
              } ${isRunning ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105'}`}
              title={s.description}
            >
              <div className="flex items-center gap-1">
                <span>{s.icon}</span>
                <span className="truncate">{s.name}</span>
              </div>
            </button>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-2">
          {scenarios.find(s => s.id === scenario)?.description}
        </p>
      </div>

      {/* Configuration Sliders */}
      <div className="space-y-3">
        <SliderInput
          label="Capacity"
          value={capacity}
          onChange={handleCapacityChange}
          min={50}
          max={300}
          step={10}
        />
        <SliderInput
          label="Initial Indoor"
          value={initialIndoor}
          onChange={(e) => setInitialIndoor(parseInt(e.target.value))}
          min={0}
          max={100}
          step={5}
          disabled={isRunning}
        />
        <SliderInput
          label="Initial Outdoor"
          value={initialOutdoor}
          onChange={(e) => setInitialOutdoor(parseInt(e.target.value))}
          min={0}
          max={50}
          step={5}
          disabled={isRunning}
        />
        <SliderInput
          label="Spawn Rate (agents/sec)"
          value={spawnRate}
          onChange={handleSpawnRateChange}
          min={0.5}
          max={8}
          step={0.5}
        />
      </div>

      {/* Main Control Buttons */}
      <div className="grid grid-cols-2 gap-2">
        {!isRunning ? (
          <>
            <button
              onClick={handleStart}
              className="col-span-2 px-4 py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg transition-all hover:scale-105"
            >
              ▶ Start Simulation
            </button>
          </>
        ) : (
          <>
            {isPaused ? (
              <button
                onClick={onResume}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium rounded transition-all"
              >
                ▶ Resume
              </button>
            ) : (
              <button
                onClick={onPause}
                className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white font-medium rounded transition-all"
              >
                ⏸ Pause
              </button>
            )}
            <button
              onClick={onStop}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-medium rounded transition-all"
            >
              ⏹ Stop
            </button>
          </>
        )}
      </div>

      {/* Reset Button - More Prominent */}
      {!isRunning && simState?.tick > 0 && (
        <div className="pt-3 border-t border-sim-border">
          <button
            onClick={onReset}
            className="w-full px-4 py-3 bg-gradient-to-r from-gray-700 to-gray-600 hover:from-gray-600 hover:to-gray-500 text-white font-bold rounded-lg transition-all hover:scale-105 shadow-lg"
          >
            🔄 RESET SIMULATION
          </button>
        </div>
      )}

      {/* Action Buttons */}
      {isRunning && (
        <div className="space-y-2 pt-2 border-t border-sim-border">
          <button
            onClick={onInjectPanic}
            disabled={isPaused}
            className="w-full px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white font-medium rounded transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            💥 Inject Panic
          </button>
          {scenario !== 3 && (
            <button
              onClick={onStartEvacuation}
              disabled={isPaused}
              className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              🚨 Start Evacuation
            </button>
          )}
        </div>
      )}

      {/* Visualization Toggles */}
      <div className="pt-3 border-t border-sim-border">
        <label className="block text-sm text-gray-400 mb-2 font-medium">Visualization</label>
        <div className="space-y-2">
          <ToggleSwitch
            label="Heatmap Overlay"
            checked={showHeatmap}
            onChange={setShowHeatmap}
          />
          <ToggleSwitch
            label="Velocity Vectors"
            checked={showVelocity}
            onChange={setShowVelocity}
          />
        </div>
      </div>

      {/* Simulation Stats */}
      {simState && (
        <div className="pt-3 border-t border-sim-border">
          <div className="text-xs text-gray-400 space-y-1">
            <div className="flex justify-between">
              <span>FPS:</span>
              <span className="text-emerald-400 font-mono">~15</span>
            </div>
            <div className="flex justify-between">
              <span>Total Agents:</span>
              <span className="text-white font-mono">{(simState.indoor_count || 0) + (simState.outdoor_count || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span>Tick:</span>
              <span className="text-white font-mono">{simState.tick || 0}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SliderInput({ label, value, onChange, min, max, step, disabled }) {
  return (
    <div>
      <div className="flex justify-between mb-1">
        <label className="text-sm text-gray-400">{label}</label>
        <span className="text-sm font-mono text-white">{value}</span>
      </div>
      <input
        type="range"
        value={value}
        onChange={onChange}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        className={`w-full h-2 bg-sim-darker rounded-lg appearance-none cursor-pointer 
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        style={{
          background: `linear-gradient(to right, #3b82f6 0%, #3b82f6 ${((value - min) / (max - min)) * 100}%, #252540 ${((value - min) / (max - min)) * 100}%, #252540 100%)`
        }}
      />
    </div>
  );
}

function ToggleSwitch({ label, checked, onChange }) {
  return (
    <label className="flex items-center justify-between cursor-pointer">
      <span className="text-sm text-gray-300">{label}</span>
      <div className="relative">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="sr-only"
        />
        <div className={`w-10 h-5 rounded-full transition-colors ${
          checked ? 'bg-blue-600' : 'bg-gray-600'
        }`}>
          <div className={`absolute left-0.5 top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
            checked ? 'translate-x-5' : 'translate-x-0'
          }`} />
        </div>
      </div>
    </label>
  );
}
