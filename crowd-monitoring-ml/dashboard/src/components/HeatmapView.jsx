import { useMemo } from 'react';

export default function HeatmapView({ densityData, persons, anomaly }) {
  const heatmapCells = useMemo(() => {
    const cells = [];
    const gridSize = 10;
    const highDensityRegions = densityData?.high_density_regions || [];
    
    for (let y = 0; y < gridSize; y++) {
      for (let x = 0; x < gridSize; x++) {
        const cellCenterX = (x + 0.5) * (640 / gridSize);
        const cellCenterY = (y + 0.5) * (480 / gridSize);
        let intensity = 0.1;
        
        for (const region of highDensityRegions) {
          const [rx, ry, density] = region;
          const dist = Math.sqrt((cellCenterX - rx) ** 2 + (cellCenterY - ry) ** 2);
          if (dist < 100) {
            intensity = Math.max(intensity, density / 10);
          }
        }
        
        cells.push({ x: x * (100 / gridSize), y: y * (100 / gridSize), width: 100 / gridSize, height: 100 / gridSize, intensity: Math.min(intensity, 1) });
      }
    }
    return cells;
  }, [densityData]);

  const getIntensityColor = (intensity) => {
    if (intensity < 0.3) return 'rgba(34, 197, 94, 0.3)';
    if (intensity < 0.6) return 'rgba(245, 158, 11, 0.5)';
    return 'rgba(239, 68, 68, 0.7)';
  };

  return (
    <div className="relative bg-dark rounded-lg overflow-hidden" style={{ height: 400 }}>
      <svg viewBox="0 0 100 100" className="w-full h-full" preserveAspectRatio="none">
        {heatmapCells.map((cell, i) => (
          <rect key={i} x={cell.x} y={cell.y} width={cell.width} height={cell.height} fill={getIntensityColor(cell.intensity)} />
        ))}
        {persons?.map((person, i) => {
          const x = (person.bbox[0] + person.bbox[2]) / 2 / 6.4;
          const y = (person.bbox[1] + person.bbox[3]) / 2 / 4.8;
          return <circle key={i} cx={x} cy={y} r={1.5} fill="#3b82f6" stroke="#fff" strokeWidth={0.3} />;
        })}
      </svg>

      <div className="absolute top-3 left-3 space-y-2">
        <div className="bg-dark/80 px-3 py-1 rounded text-sm">
          <span className="text-gray-400">Count: </span>
          <span className="font-bold">{Math.round(densityData?.count || 0)}</span>
        </div>
        <div className="bg-dark/80 px-3 py-1 rounded text-sm">
          <span className="text-gray-400">Peak: </span>
          <span className="font-bold">{(densityData?.peak_density || 0).toFixed(2)}</span>
        </div>
      </div>

      {anomaly?.detected && (
        <div className="absolute top-3 right-3 bg-danger/90 px-3 py-2 rounded-lg animate-pulse">
          <div className="font-bold text-white">⚠️ {anomaly.type.toUpperCase()}</div>
          <div className="text-xs text-white/80">Confidence: {(anomaly.confidence * 100).toFixed(0)}%</div>
        </div>
      )}

      <div className="absolute bottom-3 left-3 flex gap-3 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded" style={{ background: 'rgba(34, 197, 94, 0.5)' }} />
          <span className="text-gray-400">Low</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded" style={{ background: 'rgba(245, 158, 11, 0.5)' }} />
          <span className="text-gray-400">Medium</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded" style={{ background: 'rgba(239, 68, 68, 0.7)' }} />
          <span className="text-gray-400">High</span>
        </div>
      </div>

      {!densityData && (
        <div className="absolute inset-0 flex items-center justify-center bg-dark/50">
          <span className="text-gray-500">Waiting for camera feed...</span>
        </div>
      )}
    </div>
  );
}
