export default function DroneStatus({ gps, timing, falls }) {
  const formatCoord = (val) => val?.toFixed(6) || 'N/A';

  return (
    <div className="card">
      <h3 className="font-bold mb-3">Drone Status</h3>

      <div className="mb-4">
        <div className="text-xs text-gray-400 mb-2">📍 GPS Position</div>
        {gps ? (
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div><span className="text-gray-400">Lat:</span><span className="ml-2 font-mono">{formatCoord(gps.lat)}</span></div>
            <div><span className="text-gray-400">Lng:</span><span className="ml-2 font-mono">{formatCoord(gps.lng)}</span></div>
            <div><span className="text-gray-400">Alt:</span><span className="ml-2 font-mono">{gps.alt?.toFixed(1)}m</span></div>
            <div><span className="text-gray-400">Sats:</span><span className="ml-2 font-mono">{gps.satellites || 'N/A'}</span></div>
          </div>
        ) : (
          <div className="text-gray-500 text-sm">No GPS fix</div>
        )}
        {gps && (
          <a href={`https://maps.google.com/?q=${gps.lat},${gps.lng}`} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline mt-2 block">
            Open in Google Maps →
          </a>
        )}
      </div>

      <div className="mb-4">
        <div className="text-xs text-gray-400 mb-2">⚡ Inference Timing</div>
        {timing ? (
          <div className="space-y-1">
            <TimingRow label="Pose" value={timing.pose} />
            <TimingRow label="Fall Detection" value={timing.fall} />
            <TimingRow label="Density" value={timing.density} />
            <TimingRow label="Optical Flow" value={timing.flow} />
            <div className="border-t border-border pt-1 mt-1">
              <TimingRow label="Total" value={timing.total} bold />
            </div>
          </div>
        ) : (
          <div className="text-gray-500 text-sm">No timing data</div>
        )}
      </div>

      <div>
        <div className="text-xs text-gray-400 mb-2">🚨 Fall Detection</div>
        {falls && falls.length > 0 ? (
          <div className="space-y-2">
            {falls.map((fall, i) => (
              <div key={i} className={`p-2 rounded text-sm ${fall.confirmed ? 'bg-danger/20 border border-danger' : 'bg-warning/20 border border-warning'}`}>
                <div className="font-medium">Person {fall.person_id}: {fall.state}</div>
                <div className="text-xs text-gray-400">Confidence: {(fall.confidence * 100).toFixed(0)}%{fall.duration > 0 && ` • ${fall.duration.toFixed(1)}s`}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-success text-sm flex items-center gap-2">
            <span className="w-2 h-2 bg-success rounded-full"></span>
            No falls detected
          </div>
        )}
      </div>
    </div>
  );
}

function TimingRow({ label, value, bold = false }) {
  const getColor = (ms) => {
    if (ms < 20) return 'text-success';
    if (ms < 50) return 'text-warning';
    return 'text-danger';
  };

  return (
    <div className="flex justify-between text-sm">
      <span className={`text-gray-400 ${bold ? 'font-bold' : ''}`}>{label}</span>
      <span className={`font-mono ${bold ? 'font-bold' : ''} ${getColor(value || 0)}`}>{(value || 0).toFixed(1)} ms</span>
    </div>
  );
}
