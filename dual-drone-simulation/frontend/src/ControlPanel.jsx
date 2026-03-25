import { useState } from 'react';

export default function ControlPanel({
  onStart,
  onStop,
  onPause,
  onResume,
  onInjectPanic,
  onStartEvacuation,
  onCapacityChange,
  onSpawnRateChange,
  isRunning,
  isPaused,
}) {
  const [scenario, setScenario] = useState(1);
  const [capacity, setCapacity] = useState(100);
  const [initialIndoor, setInitialIndoor] = useState(20);
  const [initialOutdoor, setInitialOutdoor] = useState(10);
  const [spawnRate, setSpawnRate] = useState(2.0);

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
      <h3 className="font-bold text-lg text-white">Simulation Control</h3>

      {/* Scenario Selection */}
      <div>
        <label className="block text-sm text-gray-400 mb-2">Scenario</label>
        <div className="grid grid-cols-3 gap-2">
          {[1, 2, 3].map((s) => (
            <button
              key={s}
              onClick={() => setScenario(s)}
              disabled={isRunning}
              className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
                scenario === s
                  ? 'bg-blue-600 text-white'
                  : 'bg-sim-darker text-gray-300 hover:bg-sim-border'
              } ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {s === 1 ? 'Entry+Exit' : s === 2 ? 'Entry Only' : 'Evacuation'}
            </button>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {scenario === 1 && 'Steady state with entry and exit flows'}
          {scenario === 2 && 'Entry only - tests capacity limits'}
          {scenario === 3 && 'Emergency evacuation scenario'}
        </p>
      </div>

      {/* Configuration Sliders */}
      <div className="space-y-3">
        <SliderInput
          label="Capacity"
          value={capacity}
          onChange={handleCapacityChange}
          min={50}
          max={200}
          step={10}
        />
        <SliderInput
          label="Initial Indoor"
          value={initialIndoor}
          onChange={(e) => setInitialIndoor(parseInt(e.target.value))}
          min={0}
          max={50}
          step={5}
          disabled={isRunning}
        />
        <SliderInput
          label="Initial Outdoor"
          value={initialOutdoor}
          onChange={(e) => setInitialOutdoor(parseInt(e.target.value))}
          min={0}
          max={30}
          step={5}
          disabled={isRunning}
        />
        <SliderInput
          label="Spawn Rate (agents/sec)"
          value={spawnRate}
          onChange={handleSpawnRateChange}
          min={0.5}
          max={5}
          step={0.5}
        />
      </div>

      {/* Control Buttons */}
      <div className="grid grid-cols-2 gap-2">
        {!isRunning ? (
          <button
            onClick={handleStart}
            className="col-span-2 px-4 py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg transition-colors"
          >
            ▶ Start Simulation
          </button>
        ) : (
          <>
            {isPaused ? (
              <button
                onClick={onResume}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium rounded transition-colors"
              >
                ▶ Resume
              </button>
            ) : (
              <button
                onClick={onPause}
                className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white font-medium rounded transition-colors"
              >
                ⏸ Pause
              </button>
            )}
            <button
              onClick={onStop}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-medium rounded transition-colors"
            >
              ⏹ Stop
            </button>
          </>
        )}
      </div>

      {/* Action Buttons */}
      {isRunning && (
        <div className="space-y-2 pt-2 border-t border-sim-border">
          <button
            onClick={onInjectPanic}
            className="w-full px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white font-medium rounded transition-colors"
          >
            💥 Inject Panic (Click on Canvas)
          </button>
          {scenario !== 3 && (
            <button
              onClick={onStartEvacuation}
              className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded transition-colors"
            >
              🚨 Start Evacuation
            </button>
          )}
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
