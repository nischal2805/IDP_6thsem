# Scenario Quick Reference Guide

## How to Identify Each Scenario When Running

### Scenario 1: Entry + Exit ↔️
```
Outdoor Queue → Entry Door → Indoor Space → Top Exit
```
**Observable**: Steady flow of agents from bottom to top. Balanced entry/exit.

---

### Scenario 2: Entry Only ➡️
```
Outdoor Queue → Entry Door → Indoor Space (NO EXIT)
```
**Observable**: 
- Indoor crowd density increases over time
- Agents wander randomly inside
- Higher spawn rate (3.0/sec) accelerates filling
- Eventually reaches capacity and gate closes

---

### Scenario 3: Emergency Evacuation 🚨
```
                    ← Left Emergency Exit
Indoor Crowd (50+)  ← Main Door Exit (bottom)
                    ← Right Emergency Exit
```
**Observable**:
- All agents have `is_panicking = True`
- No new spawns (spawn_rate = 0.0)
- Gate closed
- Agents rush to nearest of 3 exits
- Crush compression at exit points

**Exit Locations**:
- Main: (DOOR_X, y=0)
- Left: (x=0, y=10)
- Right: (x=20, y=10)

---

### Scenario 7: Bidirectional Flow ⇄
```
MODE: ENTRY (0-10s)
Outdoor Queue → Door → Indoor (wandering)

MODE: EXIT (10-20s)  
Indoor → Door → Outdoor (removed)

(Alternates every 10 seconds)
```
**Observable**:
- Mode switches visible in logs: `bidirectional_mode = "entry"/"exit"`
- During EXIT mode:
  - All indoor agents goal → door
  - No new outdoor spawns
- During ENTRY mode:
  - Outdoor agents enter
  - Indoor agents wander randomly
- Lower spawn rate (1.5/sec) to prevent overwhelming counter-flow

---

## Code Checkpoints for Each Scenario

### Scenario 1: Entry + Exit
```python
# Goal assignment in _handle_door_transitions()
if self.scenario == 1:
    agent.goal_x = EXIT_X  # 10.0
    agent.goal_y = INDOOR_HEIGHT + 1  # 21.0

# Exit handling in step()
if scenario_type == "basic":
    self._handle_exits()  # Top wall exit
```

### Scenario 2: Entry Only
```python
# No exit flag
has_exit = False

# Higher spawn rate
spawn_rate = 3.0

# Wandering goal updates
self._update_wandering_goals()
```

### Scenario 3: Evacuation
```python
# Triggered by start_evacuation()
agent.is_panicking = True
self._assign_evacuation_exit(agent)

# 3-way exit calculation
dist_main = agent.y
dist_left = sqrt(x² + (y - 10)²)
dist_right = sqrt((x - 20)² + (y - 10)²)
# Assign to minimum distance
```

### Scenario 7: Bidirectional
```python
# Mode tracking
self.bidirectional_mode = "entry"  # or "exit"
self.bidirectional_timer = 0.0
self.bidirectional_interval = 10.0

# Mode switch logic in step()
if self.bidirectional_timer >= self.bidirectional_interval:
    if self.bidirectional_mode == "entry":
        self._switch_to_exit_mode()  # Send indoor → door
    else:
        self._switch_to_entry_mode()  # Resume entry
```

---

## Testing Each Scenario

### Manual Test Commands
```python
# Test Scenario 1
sim = CrowdSimulation(1)
sim.spawn_initial_crowd()
sim.step(gate_open=True)
# Check: Indoor agents should have goal_y = 21.0 (top exit)

# Test Scenario 2
sim = CrowdSimulation(2)
sim.spawn_initial_crowd()
for _ in range(50):
    sim.step(gate_open=True)
# Check: Indoor count should increase, no exits

# Test Scenario 3
sim = CrowdSimulation(3)
sim.spawn_initial_crowd()
sim.start_evacuation()
# Check: All agents is_panicking = True
# Check: Goals point to 3 different exits

# Test Scenario 7
sim = CrowdSimulation(7)
sim.spawn_initial_crowd()
# At t=0: bidirectional_mode = "entry"
for _ in range(150):  # 15 seconds at 0.1s steps
    sim.step(dt=0.1, gate_open=True)
# At t=15: Should have switched to "exit" mode
```

---

## Spawn Rate Comparison

| Scenario | Spawn Rate | Reason |
|----------|-----------|--------|
| 1 | 2.0/sec | Balanced entry/exit flow |
| 2 | 3.0/sec | Accelerate capacity filling |
| 3 | 0.0/sec | No entry during evacuation |
| 4 | 2.0/sec | Default (stadium sections) |
| 5 | 4.0/sec | Multi-lane parallel entry |
| 6 | 2.5/sec | Tiered admission |
| 7 | 1.5/sec | Counter-flow management |
| 8 | 2.0/sec | Default (predictive) |

---

## Scenario Type Mapping

```python
SCENARIOS = {
    1: "basic" + has_exit,
    2: "basic" + no_exit,
    3: "evacuation",
    4: "stadium",
    5: "multi_lane",
    6: "tiered",
    7: "bidirectional",
    8: "predictive"
}
```

---

## Debug Output Examples

### Scenario 1
```
Scenario: 1 (Entry + Exit)
Spawn rate: 2.0/sec
Indoor agents: 20 → 18 → 15 (exiting)
Sample goal: (10.0, 21.0)  # Top exit
```

### Scenario 2
```
Scenario: 2 (Entry Only)
Spawn rate: 3.0/sec
Indoor agents: 10 → 15 → 25 → 40 (accumulating)
Sample goal: (12.4, 7.8)  # Random wandering
```

### Scenario 3
```
Scenario: 3 (Evacuation)
Spawn rate: 0.0/sec
Gate: CLOSED
Panicking: 50/50 agents
Exits: Main(33%), Left(34%), Right(33%)
```

### Scenario 7
```
Scenario: 7 (Bidirectional)
Spawn rate: 1.5/sec
Mode: entry (5.2s / 10.0s)
  → Indoor wandering, outdoor entering
Mode: exit (2.1s / 10.0s)
  → Indoor exiting, no spawns
```

---

## Future Enhancement Hooks

### Zone-Based Scenarios (4, 5, 6)
```python
# Already exists in sim_server.py
zone_manager = ZoneManager()
zone_manager.assign_zone(agent_id, zone_id)
zone_manager.check_capacity(zone_id)
```

### Predictive Control (8)
```python
# Placeholder for ML integration
def predict_congestion(density_history):
    # ML model here
    return congestion_level

if congestion_level > threshold:
    gate_open = False
```

---

**Quick Scenario Selection Test**:
```bash
cd D:\IDP\dual-drone-simulation\backend
python test_scenarios.py
```
