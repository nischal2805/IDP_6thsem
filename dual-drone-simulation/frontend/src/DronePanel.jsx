export default function DronePanel({ droneData, status }) {
  if (!droneData) return null;

  const isEvacuating = droneData.evacuation_mode;
  const isDroneA = droneData.drone === 'A';

  return (
    <div className={`bg-sim-card rounded-lg p-4 border-2 status-ring status-${status}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${isDroneA ? 'bg-blue-500' : 'bg-emerald-500'}`} />
          <h3 className="font-bold text-lg">Drone {droneData.drone}</h3>
        </div>
        <span className="text-sm text-gray-400">{droneData.zone}</span>
      </div>

      <div className="text-sm text-gray-300 mb-3">{droneData.role}</div>

      <div className="space-y-2">
        {isDroneA ? (
          <>
            <MetricRow 
              label="Indoor Count" 
              value={droneData.monitoring?.indoor_count || 0} 
              max={droneData.monitoring?.capacity || 100}
            />
            <MetricRow 
              label="Capacity" 
              value={droneData.monitoring?.capacity || 100} 
            />
            <MetricRow 
              label="Crush Risk" 
              value={(droneData.monitoring?.crush_risk || 0).toFixed(2)} 
              warning={droneData.monitoring?.crush_risk >= 4}
            />
          </>
        ) : (
          <>
            <MetricRow 
              label="Outdoor Count" 
              value={droneData.monitoring?.outdoor_count || 0} 
            />
            <MetricRow 
              label="Gate Queue" 
              value={droneData.monitoring?.gate_queue || 0} 
            />
            <div className="flex items-center justify-between pt-2 border-t border-sim-border">
              <span className="text-gray-400">Gate Status</span>
              <span className={`px-2 py-1 rounded text-xs font-bold gate-indicator gate-${droneData.gate_command}`}>
                {droneData.gate_command}
              </span>
            </div>
            {droneData.throttle_active && (
              <div className="text-xs text-yellow-400">⚡ Throttle Active</div>
            )}
          </>
        )}
      </div>

      {isEvacuating && (
        <div className="mt-3 pt-3 border-t border-sim-border">
          <div className="text-sm text-blue-400 font-bold">🚨 EVACUATION MODE</div>
        </div>
      )}
    </div>
  );
}

function MetricRow({ label, value, max, warning }) {
  const percentage = max ? Math.round((value / max) * 100) : null;
  
  return (
    <div className="flex items-center justify-between">
      <span className="text-gray-400">{label}</span>
      <div className="flex items-center gap-2">
        <span className={`font-mono ${warning ? 'text-red-400' : 'text-white'}`}>
          {value}
        </span>
        {percentage !== null && (
          <span className="text-xs text-gray-500">({percentage}%)</span>
        )}
      </div>
    </div>
  );
}
