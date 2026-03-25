import { useState } from 'react';

export default function ReplayControls({ history, onExport }) {
  const [isReplaying, setIsReplaying] = useState(false);
  const [replayIndex, setReplayIndex] = useState(0);

  const handleExport = () => {
    if (!history || history.length === 0) return;

    // Convert to CSV
    const headers = ['tick', 'indoor_count', 'outdoor_count', 'status', 'crush_risk_index'];
    const rows = history.map(h => [
      h.tick,
      h.indoor_count,
      h.outdoor_count,
      h.status,
      h.crush_risk_index
    ]);

    const csv = [
      headers.join(','),
      ...rows.map(r => r.join(','))
    ].join('\n');

    // Download
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `simulation_history_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    if (onExport) onExport();
  };

  return (
    <div className="bg-sim-card rounded-lg p-4 border border-sim-border">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-gray-300">Replay & Export</h3>
        <span className="text-xs text-gray-500">
          {history?.length || 0} ticks recorded
        </span>
      </div>

      {/* Replay Slider */}
      <div className="mb-3">
        <input
          type="range"
          min={0}
          max={Math.max(0, (history?.length || 1) - 1)}
          value={replayIndex}
          onChange={(e) => setReplayIndex(parseInt(e.target.value))}
          disabled={!isReplaying || !history?.length}
          className="w-full h-2 bg-sim-darker rounded-lg appearance-none cursor-pointer"
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>Tick 0</span>
          <span>Tick {history?.length - 1 || 0}</span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex gap-2">
        <button
          onClick={() => setIsReplaying(!isReplaying)}
          disabled={!history?.length}
          className={`flex-1 px-3 py-2 rounded text-sm font-medium transition-colors ${
            isReplaying
              ? 'bg-yellow-600 hover:bg-yellow-700 text-white'
              : 'bg-sim-darker hover:bg-sim-border text-gray-300'
          } ${!history?.length ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {isReplaying ? '⏸ Exit Replay' : '⏪ Replay Mode'}
        </button>
        <button
          onClick={handleExport}
          disabled={!history?.length}
          className={`flex-1 px-3 py-2 bg-sim-darker hover:bg-sim-border text-gray-300 rounded text-sm font-medium transition-colors
            ${!history?.length ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          📥 Export CSV
        </button>
      </div>

      {/* Replay info */}
      {isReplaying && history?.length > 0 && (
        <div className="mt-3 p-2 bg-sim-darker rounded text-sm">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-gray-500">Tick:</span>
              <span className="ml-2 font-mono">{history[replayIndex]?.tick}</span>
            </div>
            <div>
              <span className="text-gray-500">Indoor:</span>
              <span className="ml-2 font-mono">{history[replayIndex]?.indoor_count}</span>
            </div>
            <div>
              <span className="text-gray-500">Status:</span>
              <span className="ml-2 font-mono">{history[replayIndex]?.status}</span>
            </div>
            <div>
              <span className="text-gray-500">Crush:</span>
              <span className="ml-2 font-mono">{history[replayIndex]?.crush_risk_index}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
