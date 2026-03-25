export default function CrushRiskGauge({ crushRisk, warning, critical, scenarioType }) {
  const maxRisk = 8;
  const percentage = Math.min((crushRisk / maxRisk) * 100, 100);
  
  const isEvacuation = scenarioType === 'evacuation';
  
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

  const getStatusMessage = () => {
    // During evacuation, high crush risk at exits is NORMAL behavior
    if (isEvacuation) {
      if (critical) {
        return {
          level: 'EVAC CRITICAL',
          message: '🚨 Extreme exit compression - staged evacuation in progress to manage flow.',
          bgColor: 'bg-orange-500/10',
          borderColor: 'border-orange-500/30',
          textColor: 'text-orange-400'
        };
      }
      if (warning) {
        return {
          level: 'EVAC HIGH',
          message: '⚡ High exit compression expected during evacuation. System managing flow.',
          bgColor: 'bg-yellow-500/10',
          borderColor: 'border-yellow-500/30',
          textColor: 'text-yellow-400'
        };
      }
      return {
        level: 'EVAC NORMAL',
        message: '✓ Evacuation proceeding. Exit compression within expected range.',
        bgColor: 'bg-blue-500/10',
        borderColor: 'border-blue-500/30',
        textColor: 'text-blue-400'
      };
    }
    
    // Normal operation (not evacuation)
    if (critical) {
      return {
        level: 'CRITICAL',
        message: '⚠️ Dangerous crowd compression! Immediate intervention required.',
        bgColor: 'bg-red-500/10',
        borderColor: 'border-red-500/30',
        textColor: 'text-red-400'
      };
    }
    if (warning) {
      return {
        level: 'WARNING',
        message: '⚡ Elevated crowd density detected. Monitor closely and prepare throttling.',
        bgColor: 'bg-yellow-500/10',
        borderColor: 'border-yellow-500/30',
        textColor: 'text-yellow-400'
      };
    }
    if (crushRisk < 1.5) {
      return {
        level: 'OPTIMAL',
        message: '✓ Crowd density is at safe levels. No action required.',
        bgColor: 'bg-emerald-500/10',
        borderColor: 'border-emerald-500/30',
        textColor: 'text-emerald-400'
      };
    }
    return {
      level: 'NORMAL',
      message: '• Crowd density within acceptable range. Continue monitoring.',
      bgColor: 'bg-blue-500/10',
      borderColor: 'border-blue-500/30',
      textColor: 'text-blue-400'
    };
  };

  const status = getStatusMessage();

  return (
    <div className="bg-sim-card rounded-lg p-4 border border-sim-border">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-gray-300">Crush Risk Index</h3>
        <span className={`px-2 py-1 ${status.bgColor} ${status.textColor} text-xs font-bold rounded ${
          critical ? 'animate-pulse' : ''
        }`}>
          {status.level}
        </span>
      </div>

      {/* Gauge bar */}
      <div className="relative h-6 bg-sim-darker rounded-full overflow-hidden mb-2">
        {/* Threshold markers */}
        <div 
          className="absolute top-0 bottom-0 w-0.5 bg-yellow-500/50 z-10"
          style={{ left: `${(3 / maxRisk) * 100}%` }}
          title="Warning threshold: 3.0"
        />
        <div 
          className="absolute top-0 bottom-0 w-0.5 bg-red-500/50 z-10"
          style={{ left: `${(6 / maxRisk) * 100}%` }}
          title="Critical threshold: 6.0"
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
        <span className="text-emerald-500">Safe (&lt;3)</span>
        <span className="text-yellow-500">Warning (≥3)</span>
        <span className="text-red-500">Critical (≥6)</span>
      </div>

      {/* Status message */}
      <div className={`mt-3 p-2 ${status.bgColor} border ${status.borderColor} rounded text-xs ${status.textColor}`}>
        {status.message}
      </div>
    </div>
  );
}
