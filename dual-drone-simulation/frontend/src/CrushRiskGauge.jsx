export default function CrushRiskGauge({ crushRisk, warning, critical }) {
  const maxRisk = 8;
  const percentage = Math.min((crushRisk / maxRisk) * 100, 100);
  
  const getColor = () => {
    if (critical) return 'bg-red-500';
    if (warning) return 'bg-yellow-500';
    if (crushRisk > 2) return 'bg-emerald-400';
    return 'bg-emerald-500';
  };

  const getTextColor = () => {
    if (critical) return 'text-red-400';
    if (warning) return 'text-yellow-400';
    return 'text-emerald-400';
  };

  return (
    <div className="bg-sim-card rounded-lg p-4 border border-sim-border">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-gray-300">Crush Risk Index</h3>
        {critical && (
          <span className="px-2 py-1 bg-red-500/20 text-red-400 text-xs font-bold rounded animate-pulse">
            CRITICAL
          </span>
        )}
        {warning && !critical && (
          <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 text-xs font-bold rounded">
            HIGH
          </span>
        )}
      </div>

      {/* Gauge bar */}
      <div className="relative h-6 bg-sim-darker rounded-full overflow-hidden mb-2">
        {/* Threshold markers */}
        <div 
          className="absolute top-0 bottom-0 w-0.5 bg-yellow-500/50 z-10"
          style={{ left: `${(4 / maxRisk) * 100}%` }}
        />
        <div 
          className="absolute top-0 bottom-0 w-0.5 bg-red-500/50 z-10"
          style={{ left: `${(6 / maxRisk) * 100}%` }}
        />
        
        {/* Fill bar */}
        <div 
          className={`h-full ${getColor()} transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Value display */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500">0</span>
        <span className={`text-2xl font-bold font-mono ${getTextColor()}`}>
          {crushRisk.toFixed(2)}
        </span>
        <span className="text-xs text-gray-500">{maxRisk}+</span>
      </div>

      {/* Legend */}
      <div className="flex justify-between mt-2 text-xs text-gray-500">
        <span>Safe</span>
        <span className="text-yellow-500">Warning (&gt;4)</span>
        <span className="text-red-500">Critical (&gt;6)</span>
      </div>

      {critical && (
        <div className="mt-3 p-2 bg-red-500/10 border border-red-500/30 rounded text-sm text-red-400">
          ⚠️ Dangerous crowd compression detected! Immediate action required.
        </div>
      )}
    </div>
  );
}
