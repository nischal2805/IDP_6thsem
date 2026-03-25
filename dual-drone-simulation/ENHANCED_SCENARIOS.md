# Enhanced Scenario System - Multi-Situation Crowd Management

## Current Implementation
- **Scenario 1**: Entry + Exit (steady state)
- **Scenario 2**: Entry Only (accumulation test)
- **Scenario 3**: Emergency Evacuation

## Proposed Enhanced Scenarios

### 1. Stadium with Reserved Sections
**Use Case**: Concert venue, sports stadium with ticketed sections

**Features**:
- Multiple zones (A, B, C, D) with individual capacity limits
- Section assignment based on ticket type
- Redirection when section reaches 80% capacity
- Cross-section monitoring to prevent overflow

**Logic**:
```python
sections = {
    'A': {'capacity': 50, 'current': 0, 'position': (5, 5)},
    'B': {'capacity': 50, 'current': 0, 'position': (15, 5)},
    'C': {'capacity': 50, 'current': 0, 'position': (5, 15)},
    'D': {'capacity': 50, 'current': 0, 'position': (15, 15)}
}

# Redirection logic
if section['current'] >= section['capacity'] * 0.8:
    redirect_to_next_available_section()
```

### 2. Queue Management with Multiple Entry Points
**Use Case**: Airport security, theme park rides, festival gates

**Features**:
- 3-4 parallel entry lanes
- Load balancing across lanes
- Dynamic lane opening/closing based on queue length
- Predicted wait time per lane

**Logic**:
```python
lanes = [
    {'id': 1, 'queue_size': 0, 'active': True},
    {'id': 2, 'queue_size': 0, 'active': True},
    {'id': 3, 'queue_size': 0, 'active': False}
]

# Auto-activate lane when others are congested
if max(active_lane_queues) > THRESHOLD:
    activate_additional_lane()
```

### 3. Progressive Flow Control (Mall/Subway)
**Use Case**: Shopping mall during sale, subway platform

**Features**:
- Predictive density mapping
- Early warning system (before congestion forms)
- Staged entry based on predicted flow
- Heat map shows forming bottlenecks

**Logic**:
```python
# Predict congestion 30 seconds ahead
future_density = predict_density(current_flow_rate, dt=30)
if future_density > WARNING_THRESHOLD:
    activate_throttle_mode()
```

### 4. Bidirectional Flow Management
**Use Case**: Narrow corridors, bridges, doorways

**Features**:
- Alternating flow direction
- Counter-flow detection
- Automatic yield zones
- Flow priority based on urgency

**Logic**:
```python
# Measure flow in both directions
inflow_rate = count_agents_entering()
outflow_rate = count_agents_exiting()

# Prioritize evacuation over entry
if evacuation_active:
    close_entry_and_prioritize_exit()
```

### 5. Tiered Admission (VIP/General/Student)
**Use Case**: Events with multiple ticket tiers

**Features**:
- Priority lanes for different groups
- Staggered admission times
- VIP bypass lanes
- Occupancy limits per tier

**Logic**:
```python
agents = {
    'vip': {'priority': 1, 'quota': 20},
    'general': {'priority': 2, 'quota': 100},
    'student': {'priority': 3, 'quota': 50}
}

# Admit based on priority and quota availability
admit_next_from_priority_queue()
```

### 6. Evacuation with Staged Zones
**Use Case**: Large building evacuation (already partially implemented)

**Enhancements**:
- Floor-by-floor evacuation
- Exit capacity awareness
- Automatic zone rotation
- Panic propagation modeling (already exists)

**Logic**:
```python
# Stage evacuation by proximity to exits
zones = ['A', 'B', 'C', 'D']
current_zone = 'A'

# When zone A clears 50%, start zone B
if zone_clearance['A'] > 0.5:
    activate_zone('B')
```

## Implementation Roadmap

### Phase 1: Foundation (Current - Complete)
- ✅ Basic scenarios (1, 2, 3)
- ✅ Crush risk detection
- ✅ Throttle control
- ✅ Panic propagation

### Phase 2: Multi-Zone Support (Next Sprint)
- [ ] Define zone objects in backend
- [ ] Zone-specific capacity tracking
- [ ] Inter-zone transitions
- [ ] Zone assignment algorithm
- [ ] UI: Multi-zone visualization

### Phase 3: Predictive Logic (Future)
- [ ] Flow rate prediction
- [ ] Bottleneck detection algorithm
- [ ] Early warning triggers
- [ ] Recommendation engine

### Phase 4: Advanced Scenarios (Future)
- [ ] Multi-lane queue system
- [ ] Priority-based admission
- [ ] Bidirectional flow
- [ ] Real-time optimization

## Technical Requirements

### Backend Changes
```python
# New data structures
class Zone:
    id: str
    capacity: int
    current_count: int
    position: Tuple[float, float]
    size: Tuple[float, float]
    status: ZoneStatus
    redirect_target: Optional[str]

class MultiZoneCoordinator:
    zones: Dict[str, Zone]
    
    def assign_agent_to_zone(agent) -> Zone
    def check_redirection_needed(zone_id) -> bool
    def get_best_redirect_target(from_zone) -> Zone
```

### Frontend Changes
```jsx
// Zone visualization component
<ZoneOverlay zones={simState.zones} />

// Scenario selection with detailed configs
<ScenarioSelector 
  scenarios={ENHANCED_SCENARIOS}
  onSelect={handleScenarioSelect}
/>
```

## Configuration Files

### Scenario Config (TOML)
```toml
[scenario.stadium]
name = "Stadium with Reserved Sections"
zones = [
    {id = "A", capacity = 50, position = [5, 5], size = [8, 8]},
    {id = "B", capacity = 50, position = [15, 5], size = [8, 8]},
    {id = "C", capacity = 50, position = [5, 15], size = [8, 8]},
    {id = "D", capacity = 50, position = [15, 15], size = [8, 8]}
]
redirection_threshold = 0.8
```

## Metrics to Track

1. **Section Utilization** - Occupancy % per zone
2. **Redirection Events** - Count of automatic redirections
3. **Average Wait Time** - Per queue/section
4. **Flow Efficiency** - Throughput vs. capacity
5. **Bottleneck Duration** - Time spent in congested state
6. **Evacuation Time** - Total time to clear (by zone)

## Notes for Implementation

- Start with **Scenario 4 (Stadium)** as it builds on existing capacity logic
- Use existing `coordinator.py` state machine as template
- Add zone visualization to existing PixiJS canvas
- Keep backward compatibility with current 3 scenarios
- Add scenario selection UI in ControlPanel

---

**Status**: Planning phase - Ready for implementation when requested
**Priority**: Medium (after current UI fixes)
**Estimated Effort**: 2-3 days for basic multi-zone support
