export default function AlertFeed({ alerts, onAcknowledge }) {
  const getAlertStyle = (type) => {
    switch (type) {
      case 'fall':
        return { bg: 'bg-danger/20', border: 'border-danger', icon: '🚨', label: 'FALL DETECTED' };
      case 'panic':
        return { bg: 'bg-warning/20', border: 'border-warning', icon: '⚠️', label: 'PANIC ALERT' };
      case 'crush_risk':
        return { bg: 'bg-danger/20', border: 'border-danger', icon: '🔴', label: 'CRUSH RISK' };
      default:
        return { bg: 'bg-gray-500/20', border: 'border-gray-500', icon: 'ℹ️', label: 'ALERT' };
    }
  };

  const formatTime = (timestamp) => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString();
  };

  const activeAlerts = alerts.filter(a => !a.acknowledged);
  const acknowledgedAlerts = alerts.filter(a => a.acknowledged);

  return (
    <div className="card max-h-96 overflow-hidden flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-bold">Alert Feed</h3>
        <span className="text-xs text-gray-400">{activeAlerts.length} active</span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2">
        {alerts.length === 0 ? (
          <div className="text-gray-500 text-center py-8">No alerts</div>
        ) : (
          <>
            {activeAlerts.map((alert) => {
              const style = getAlertStyle(alert.type);
              return (
                <div key={alert.alert_id} className={`p-3 rounded-lg border ${style.bg} ${style.border} alert-pulse`}>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{style.icon}</span>
                      <div>
                        <div className="font-bold text-sm">{style.label}</div>
                        <div className="text-xs text-gray-400">{alert.alert_id} • {formatTime(alert.timestamp)}</div>
                      </div>
                    </div>
                    <button onClick={() => onAcknowledge(alert.alert_id)} className="text-xs px-2 py-1 bg-white/10 hover:bg-white/20 rounded">
                      ACK
                    </button>
                  </div>
                  {alert.location && (
                    <a href={`https://maps.google.com/?q=${alert.location.lat},${alert.location.lng}`} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline mt-2 block">
                      📍 View on Map
                    </a>
                  )}
                  <div className="text-xs text-gray-400 mt-1">Confidence: {(alert.confidence * 100).toFixed(0)}%</div>
                </div>
              );
            })}

            {acknowledgedAlerts.length > 0 && (
              <div className="border-t border-border pt-2 mt-2">
                <div className="text-xs text-gray-500 mb-2">Acknowledged</div>
                {acknowledgedAlerts.slice(0, 3).map((alert) => {
                  const style = getAlertStyle(alert.type);
                  return (
                    <div key={alert.alert_id} className="p-2 rounded bg-dark/50 text-gray-500 text-xs mb-1">
                      <span>{style.icon}</span> {alert.alert_id} - {formatTime(alert.timestamp)}
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
