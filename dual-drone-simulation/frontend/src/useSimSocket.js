import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = 'ws://localhost:8000/ws';

export function useSimSocket() {
  const [connected, setConnected] = useState(false);
  const [simState, setSimState] = useState(null);
  const [historyExport, setHistoryExport] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log('WebSocket connected');
    };

    ws.onclose = () => {
      setConnected(false);
      console.log('WebSocket disconnected');
      // Reconnect after 2 seconds
      reconnectTimeoutRef.current = setTimeout(connect, 2000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'history_export') {
          setHistoryExport(data.data);
        } else {
          setSimState(data);
        }
      } catch (e) {
        console.error('Failed to parse message:', e);
      }
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  const sendCommand = useCallback((command, params = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command, ...params }));
    }
  }, []);

  const startSimulation = useCallback((scenario = 1, capacity = 100, initialIndoor = 20, initialOutdoor = 10) => {
    sendCommand('start', { 
      scenario, 
      capacity, 
      initial_indoor: initialIndoor,
      initial_outdoor: initialOutdoor
    });
  }, [sendCommand]);

  const stopSimulation = useCallback(() => {
    sendCommand('stop');
  }, [sendCommand]);

  const pauseSimulation = useCallback(() => {
    sendCommand('pause');
  }, [sendCommand]);

  const resumeSimulation = useCallback(() => {
    sendCommand('resume');
  }, [sendCommand]);

  const injectPanic = useCallback((x, y) => {
    sendCommand('inject_panic', { x, y });
  }, [sendCommand]);

  const startEvacuation = useCallback(() => {
    sendCommand('start_evacuation');
  }, [sendCommand]);

  const setCapacity = useCallback((capacity) => {
    sendCommand('set_capacity', { capacity });
  }, [sendCommand]);

  const setSpawnRate = useCallback((rate) => {
    sendCommand('set_spawn_rate', { rate });
  }, [sendCommand]);

  const requestHistoryExport = useCallback(() => {
    sendCommand('get_history');
  }, [sendCommand]);

  return {
    connected,
    simState,
    historyExport,
    startSimulation,
    stopSimulation,
    pauseSimulation,
    resumeSimulation,
    injectPanic,
    startEvacuation,
    setCapacity,
    setSpawnRate,
    requestHistoryExport,
  };
}
