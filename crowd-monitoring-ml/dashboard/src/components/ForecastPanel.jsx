export default function ForecastPanel({ forecast }) {
  if (!forecast) {
    return (
      <div className="card h-64 flex items-center justify-center text-gray-500">
        Forecast not available
      </div>
    );
  }

  const getTrendIcon = (trend) => {
    switch (trend) {
      case 'increasing': return '📈';
      case 'decreasing': return '📉';
      default: return '➡️';
    }
  };

  const getConfidenceColor = (confidence) => {
    if (confidence > 0.8) return 'text-success';
    if (confidence > 0.5) return 'text-warning';
    return 'text-danger';
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-bold">LSTM Density Forecast</h3>
        <span className={`text-sm ${getConfidenceColor(forecast.confidence)}`}>
          {(forecast.confidence * 100).toFixed(0)}% confidence
        </span>
      </div>

      <div className="flex items-center justify-between mb-4 p-3 bg-dark rounded-lg">
        <span className="text-gray-400">Current</span>
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold">{Math.round(forecast.current)}</span>
          <span className="text-xl">{getTrendIcon(forecast.trend)}</span>
        </div>
      </div>

      <div className="space-y-3">
        <ForecastRow label="10 seconds" value={forecast.predictions?.['10s']} current={forecast.current} />
        <ForecastRow label="30 seconds" value={forecast.predictions?.['30s']} current={forecast.current} />
        <ForecastRow label="60 seconds" value={forecast.predictions?.['60s']} current={forecast.current} />
      </div>

      {forecast.warning && (
        <div className="mt-4 p-3 bg-danger/20 border border-danger/50 rounded-lg">
          <span className="text-danger text-sm font-medium">⚠️ {forecast.warning}</span>
        </div>
      )}
    </div>
  );
}

function ForecastRow({ label, value, current }) {
  const diff = value - current;
  const diffColor = diff > 5 ? 'text-danger' : diff > 0 ? 'text-warning' : 'text-success';
  const diffSign = diff > 0 ? '+' : '';

  return (
    <div className="flex items-center justify-between">
      <span className="text-gray-400 text-sm">{label}</span>
      <div className="flex items-center gap-3">
        <span className="font-mono font-bold">{Math.round(value || 0)}</span>
        <span className={`text-xs ${diffColor}`}>{diffSign}{Math.round(diff || 0)}</span>
      </div>
    </div>
  );
}
