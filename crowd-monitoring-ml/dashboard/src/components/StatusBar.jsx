export default function StatusBar({ connected, jetsonConnected, fps, frameId }) {
  return (
    <div className="flex items-center gap-6">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${connected ? 'bg-success' : 'bg-danger'}`} />
        <span className="text-sm text-gray-400">Server: {connected ? 'Connected' : 'Disconnected'}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${jetsonConnected ? 'bg-success' : 'bg-warning'}`} />
        <span className="text-sm text-gray-400">Jetson: {jetsonConnected ? 'Online' : 'Offline'}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-400">FPS:</span>
        <span className={`font-mono font-bold ${fps > 10 ? 'text-success' : 'text-warning'}`}>{fps.toFixed(1)}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-400">Frame:</span>
        <span className="font-mono text-white">{frameId}</span>
      </div>
    </div>
  );
}
