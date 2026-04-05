# Dual Drone Crowd Flow Simulation

A web-based crowd simulation demonstrating real-time coordination between two drones: **Drone A (Indoor)** monitoring crowd density inside a building, and **Drone B (Outdoor)** controlling entry at the entrance door.

## Features

- **Real-time Physics** using PySocialForce (Extended Social Force Model)
- **Three Scenarios**: Entry+Exit, Entry Only, Emergency Evacuation
- **Dual Drone Coordination**: Indoor monitoring and outdoor queue management
- **Crush Risk Detection**: Local density analysis with visual heatmaps
- **Panic Propagation**: Click to inject panic that spreads through the crowd
- **WebGL Visualization**: Smooth 60fps rendering with PixiJS
- **Live Charts**: Occupancy tracking with threshold indicators
- **Export**: CSV export of simulation history

## Tech Stack

### Backend (Python)
- **PySocialForce**: Core crowd physics engine
- **FastAPI**: WebSocket server (~15 FPS broadcast)
- **NumPy/SciPy**: Agent state arrays, Gaussian heatmaps

### Frontend (React)
- **PixiJS**: WebGL canvas rendering
- **Recharts**: Live occupancy charts
- **Tailwind CSS**: Modern UI styling

## Quick Start

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt
python sim_server.py
```

Server runs at `http://localhost:8000`

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`

## Scenarios

### Scenario 1: Entry + Exit (Steady State)
Agents enter through the front door and exit through an opening on the far wall. Demonstrates the full GREEN → YELLOW → ORANGE → RED state cycle.

### Scenario 2: Entry Only (No Exit)
No exit - indoor agents wander randomly. Occupancy increases until capacity triggers gate closure. Tests hard-cutoff behavior.

### Scenario 3: Emergency Evacuation
All indoor agents are assigned exit goals simultaneously. Entry is locked. Demonstrates crush compression at narrow exits.

## Coordinator States

| State | Trigger | Gate Command |
|-------|---------|--------------|
| GREEN | < 70% capacity | OPEN |
| YELLOW | 70-85% capacity | THROTTLE (3 per 5s) |
| ORANGE | 85-95% capacity | THROTTLE (1 per 8s) |
| RED | ≥ 95% capacity | CLOSED |
| CRITICAL | 100% capacity | CLOSED + distress |

## Controls

- **Start/Stop/Pause**: Control simulation flow
- **Scenario Selection**: Choose simulation mode
- **Capacity Slider**: Adjust building capacity
- **Spawn Rate**: Control agent arrival rate
- **Inject Panic**: Click on canvas to trigger panic wave
- **Start Evacuation**: Switch to evacuation mode

## WebSocket API

Connect to `ws://localhost:8000/ws` for real-time updates.

### Commands (client → server)
```json
{"command": "start", "scenario": 1, "capacity": 100, "initial_indoor": 20, "initial_outdoor": 10}
{"command": "stop"}
{"command": "pause"}
{"command": "resume"}
{"command": "inject_panic", "x": 10, "y": 10}
{"command": "start_evacuation"}
{"command": "set_capacity", "capacity": 150}
{"command": "set_spawn_rate", "rate": 3.0}
```

### State Broadcast (server → client)
```json
{
  "tick": 150,
  "agents": [[x, y, vx, vy, is_slow, is_panicking, behavior_state, local_density, assigned_stand], ...],
  "indoor_count": 47,
  "outdoor_count": 23,
  "capacity": 100,
  "status": "YELLOW",
  "gate": "THROTTLE",
  "crush_risk_index": 2.3,
  "indoor_heatmap": [[...]],
  "outdoor_heatmap": [[...]],
  "history": [{"t": 0, "count": 10, "crush_risk": 1.1}, ...],
  "stadium": {
    "stands": {
      "left": {"name": "Stand A (Left)", "current": 22, "capacity": 40, "gate_open": true, "utilization": 55.0},
      "center": {"name": "Stand B (Center)", "current": 36, "capacity": 50, "gate_open": true, "utilization": 72.0},
      "right": {"name": "Stand C (Right)", "current": 40, "capacity": 40, "gate_open": false, "utilization": 100.0}
    },
    "total_seated": 98,
    "total_capacity": 130,
    "all_full": false
  }
}
```

## Project Structure

```
dual-drone-simulation/
├── backend/
│   ├── sim_server.py       # FastAPI WebSocket server
│   ├── coordinator.py      # State machine logic
│   ├── crowd_sim.py        # PySocialForce wrapper
│   ├── panic.py            # Panic propagation
│   ├── heatmap.py          # Density computation
│   ├── config.toml         # Force weights
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── SimPage.jsx         # Main page
│   │   ├── FloorCanvas.jsx     # PixiJS visualization
│   │   ├── DronePanel.jsx      # Drone status panels
│   │   ├── OccupancyChart.jsx  # Recharts live chart
│   │   ├── CrushRiskGauge.jsx  # Risk indicator
│   │   ├── ControlPanel.jsx    # Simulation controls
│   │   ├── ReplayControls.jsx  # History replay
│   │   └── useSimSocket.js     # WebSocket hook
│   ├── package.json
│   └── index.html
└── README.md
```

## License

MIT
