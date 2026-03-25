# PRD 02 — Dual Drone Crowd Flow Simulation

**Project:** IDP — Crowd Simulation Module  
**Type:** Standalone web app — separate page/endpoint  
**Physics Engine:** PySocialForce (Extended Social Force Model)

---

## 1. Overview

A web-based crowd simulation demonstrating real-time coordination between two drones: Drone A (Indoor) monitoring crowd density inside a building, and Drone B (Outdoor) controlling entry at the entrance door. The simulation uses PySocialForce — a certified, published pedestrian physics library — to produce realistic crowd dynamics including group behavior, obstacle avoidance, and bottleneck formation at doorways.

Three configurable scenarios are supported, each stressing different aspects of the coordinator logic.

---

## 2. Core Physics: PySocialForce

**Library:** `pip install 'pysocialforce[test,plot]'`  
**PyPI:** pypi.org/project/PySocialForce  
**GitHub:** github.com/yuxiang-gao/PySocialForce  
**License:** MIT  
**Model:** Extended Social Force Model (Helbing & Molnar 1995 + Moussaid 2010 group extension)  
**Published in:** Journal of Open Source Software

Each agent is subject to three forces:
- **Desired force** — pushes agent toward its current goal
- **Social force** — repulsion from nearby agents to maintain personal space
- **Obstacle force** — repulsion from walls and boundaries

The library natively supports pedestrian groups, configurable obstacles, and TOML-based parameter tuning. The door bottleneck is modeled as a gap in the wall obstacle array — pressure and queue formation at the door is emergent behavior from the physics, not explicitly coded.

```python
import pysocialforce as psf

# Each row: [pos_x, pos_y, vel_x, vel_y, goal_x, goal_y]
initial_state = np.array([[1, 0, 0, 1, 1, 10], [2, 0, 0, 1, 2, 10], ...])

groups = [[0, 1], [2]]  # agent indices per group
obstacles = [[[0,0],[10,0]], [[0,0],[0,10]]]  # wall segments

sim = psf.Simulator(initial_state, groups=groups, obstacles=obstacles)
sim.step(1)
states, _ = sim.get_states()
```

### 2.1 Environment Layout

| Zone | Dimensions (sim units) | Description |
|---|---|---|
| Indoor space | 20 x 20 | Building interior, Drone A zone |
| Door/bottleneck | 2 units wide | Single chokepoint connecting zones |
| Outdoor queue zone | 20 x 15 | Waiting area, Drone B zone |
| Exit (Scenario 1 only) | 2 units wide, opposite wall | Constant-rate crowd decay |
| Emergency exits (Scenario 3) | 2x 1.5 units wide, side walls | Evacuation-only openings |

---

## 3. Scenarios

### Scenario 1 — Entry + Exit (Steady State)
Agents enter through the front door and exit through an opening on the far wall at a constant rate. Steady state is achievable when inflow rate equals outflow rate. Coordinator reacts to transient spikes. Good for demonstrating the full GREEN → YELLOW → ORANGE → RED state cycle without hard lockout.

### Scenario 2 — Entry Only (No Exit)
No exit. Indoor agents wander with random goals inside the building. Occupancy increases monotonically until Drone B triggers cutoff. Demonstrates hard-cutoff behavior and RED/CRITICAL transitions. Best for stress-testing the coordinator.

### Scenario 3 — Emergency Evacuation
All indoor agents are assigned the exit doors as goals simultaneously. Entry is immediately locked (gate CLOSED, Drone B switches to egress monitoring mode). Drone A monitors evacuation progress and compression at exit points. Drone B monitors outdoor dispersion — ensuring evacuees don't pile up directly outside.

The social force model will naturally produce dangerous crush compression at the narrow exits if the evacuation is not managed — this is the realistic emergent behavior the scenario is designed to show. The coordinator in this mode tracks:
- Evacuation completion percentage (agents remaining indoors / initial indoor count)
- Exit compression score (local density at exit openings)
- If exit compression exceeds threshold → stagger evacuation (only agents in zone A leave first, then zone B)

**Coordinator logic inversion in Scenario 3:**

| Metric | Normal Scenarios | Scenario 3 |
|---|---|---|
| Primary signal | Indoor count vs capacity | Evacuation % remaining |
| Gate command | Controls entry | Locks entry, manages exit flow |
| Drone B role | Queue management | Outdoor dispersion monitoring |
| CRITICAL trigger | 100% capacity | Exit compression > crush threshold |

---

## 4. Agent Behavior Extensions

### 4.1 Agent Demographics (Heterogeneous Crowd)
Approximately 10% of agents are assigned a lower desired velocity (0.6 m/s vs standard 1.2 m/s) representing elderly or mobility-impaired individuals. This is set at spawn time via the `desired_force.relaxation_time` parameter per agent. Effects:
- Slower agents naturally create local blockages in corridors
- Bottleneck formation at the door is more realistic and varied
- Evacuation timing in Scenario 3 is more accurate to real events
- Makes the simulation more defensible academically

No additional code required beyond setting per-agent velocity in the state array.

### 4.2 Panic Propagation Model
Panic is a spreading phenomenon rather than a one-shot button. Implementation:

**Trigger:** User clicks "Inject Panic" on the dashboard, or automatically triggered when crush risk index exceeds critical threshold.

**Propagation logic (per tick):**
- Any agent with speed > `panic_speed_threshold` (e.g. 2.0 m/s) is flagged as `PANICKING`
- Each tick, for every non-panicking agent within radius `R=3.0` of a panicking agent: assign panic state with probability `P=0.15`
- Panicking agents get their desired velocity multiplied by 2.5x, social force weights reduced (they stop caring about personal space), goal temporarily randomized

**Visual:** Panicking agents render as red dots. The panic wave spreading outward from the inject point is clearly visible as a color wave.

**Reset:** Panic state decays — after 8 seconds without re-triggering, agents revert to normal.

```python
def propagate_panic(states, panic_flags, dt):
    for i, agent in enumerate(states):
        if get_speed(agent) > PANIC_SPEED_THRESHOLD:
            panic_flags[i] = True
        if panic_flags[i]:
            neighbors = get_neighbors(states, i, radius=3.0)
            for j in neighbors:
                if not panic_flags[j] and random.random() < 0.15:
                    panic_flags[j] = True
    return panic_flags
```

---

## 5. Coordinator State Machine

### 5.1 Normal Mode (Scenarios 1 & 2)

| State | Trigger | Gate Command | Dashboard |
|---|---|---|---|
| GREEN | indoor_count < 70% capacity | OPEN | Green ring |
| YELLOW | 70% – 85% capacity | THROTTLE — 3 agents per 5s | Yellow ring |
| ORANGE | 85% – 95% capacity | THROTTLE — 1 agent per 8s | Orange ring |
| RED | >= 95% capacity | CLOSED | Red ring + alert |
| CRITICAL | 100% capacity | CLOSED + distress mode | Flashing red |

### 5.2 Evacuation Mode (Scenario 3)

| State | Trigger | Action |
|---|---|---|
| EVACUATING | Scenario 3 start | Lock gate, all agents assigned exit goals |
| STAGED | Exit compression > threshold | Split indoor zone into A/B, stagger release |
| CLEAR | Indoor count = 0 | Evacuation complete, log total time |

---

## 6. Dashboard Additions

### 6.1 Crush Risk Index
A scalar metric computed each tick independently of overall capacity percentage. Logic:
- Divide the floor plan into a 10x10 grid
- For each cell, compute local agent density (agents per unit area)
- Crush Risk Index = average density of top-5 highest-density cells
- Display as a separate gauge from the capacity ring
- Threshold: index > 4 agents/unit² → CRUSH RISK: HIGH warning

This is important because fringe density can be dangerous at 70% overall capacity — a bottleneck at the door can be crush-risk even when the room is half empty.

### 6.2 Replay + Export
- Full sim state history recorded as a rolling buffer (last 300 ticks)
- Replay button: pause live sim, scrub through history with a slider
- Export button: download full history as CSV (tick, indoor_count, outdoor_count, status, crush_risk_index)
- CSV useful for IDP report data and LSTM forecaster training

---

## 7. Tech Stack

### Backend (Python)

| Library | Install | Purpose |
|---|---|---|
| PySocialForce | `pip install pysocialforce` | Core crowd physics |
| NumPy | `pip install numpy` | Agent state arrays, density computation |
| SciPy | `pip install scipy` | Gaussian kernel for heatmaps |
| FastAPI | `pip install fastapi uvicorn` | WebSocket server, ~15 FPS broadcast |

### Frontend (React)

| Library | Install | Purpose |
|---|---|---|
| PixiJS | `npm install pixi.js` | WebGL canvas — agents, heatmap overlay |
| Recharts | `npm install recharts` | Live occupancy chart, crush risk chart |
| socket.io-client | `npm install socket.io-client` | WebSocket to Python backend |
| Tailwind CSS | `npm install tailwindcss` | UI styling |

### Heatmap Generation

```python
from scipy.ndimage import gaussian_filter
import numpy as np

def compute_heatmap(agent_positions, grid_size=50, sigma=2.0):
    heatmap = np.zeros((grid_size, grid_size))
    for x, y in agent_positions:
        xi = int(np.clip(x / world_width * grid_size, 0, grid_size - 1))
        yi = int(np.clip(y / world_height * grid_size, 0, grid_size - 1))
        heatmap[yi, xi] += 1
    return gaussian_filter(heatmap, sigma=sigma).tolist()
```

---

## 8. WebSocket Payload Schema

```json
{
  "agents": [[x, y, vx, vy, is_slow, is_panicking], ...],
  "indoor_count": 47,
  "outdoor_count": 23,
  "capacity": 100,
  "status": "YELLOW",
  "gate": "THROTTLE",
  "scenario": 1,
  "crush_risk_index": 2.3,
  "evacuation_pct": null,
  "indoor_heatmap": [[0.0, ...], ...],
  "outdoor_heatmap": [[0.0, ...], ...],
  "history": [{"t": 0, "count": 10, "crush_risk": 1.1}, ...]
}
```

---

## 9. File Structure

```
project/
├── backend/
│   ├── sim_server.py       # FastAPI WebSocket server + sim loop
│   ├── coordinator.py      # State machine, normal + evacuation mode
│   ├── crowd_sim.py        # PySocialForce wrapper, spawn/despawn, demographics
│   ├── panic.py            # Panic propagation logic
│   ├── heatmap.py          # SciPy gaussian heatmap + crush risk index
│   └── config.toml         # PySocialForce force weights
├── frontend/
│   ├── src/
│   │   ├── SimPage.jsx
│   │   ├── FloorCanvas.jsx      # PixiJS WebGL canvas
│   │   ├── DronePanel.jsx       # Drone A/B panels
│   │   ├── OccupancyChart.jsx   # Recharts live chart
│   │   ├── CrushRiskGauge.jsx   # Crush risk index display
│   │   ├── ControlPanel.jsx     # Sliders, buttons, scenario selector
│   │   ├── ReplayControls.jsx   # Scrub + export
│   │   └── useSimSocket.js      # WebSocket hook
│   └── package.json
└── README.md
```

---

## 10. PySocialForce Config

```toml
[desired_force]
factor = 1.0
goal_threshold = 0.2
relaxation_time = 0.5        # overridden per-agent for slow agents (0.9)

[social_force]
factor = 5.1
lambda_importance = 2.0
gamma = 0.35
n = 2
n_prime = 3

[obstacle_force]
factor = 10.0
sigma = 0.2

[group_coherence_force]
factor = 3.0
```

---

## 11. Known Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Agent tunneling through walls at high speed during panic | Cap max velocity at 3.5 m/s even in panic state. Increase obstacle_force sigma. |
| PixiJS performance at 500+ agents | Use PIXI.ParticleContainer for agents. Cap at 300 for demo. |
| WebSocket payload size | Quantize positions to 2 decimal places. Consider msgpack over JSON. |
| Agent pile-up at gate (not at door itself) | Apply holding line N units back. Zero velocity of agents past line, not at door threshold. |
| PySocialForce re-instantiation on agent count change | Rebuild state array each tick excluding despawned indices. Batch removals per tick. |
| Panic propagation causing all agents to panic instantly | Cap propagation probability at P=0.15, add per-agent cooldown before re-triggering. |
| Evacuation crush at narrow side exits | Implement staged evacuation zones A/B when compression detected. |
