# Evacuation Behavior - Crush Risk Explanation

## Why Crush Risk Increases During Evacuation

**This is EXPECTED and CORRECT behavior** - not a bug.

### The Physics of Evacuation

During an emergency evacuation (Scenario 3), all indoor agents simultaneously attempt to exit through limited egress points (doors). This creates:

1. **Funnel Effect**: Large crowd → narrow exit points
2. **Local Compression**: High density clusters form near exits
3. **Exit Bottleneck**: Physical constraint limits throughput

### Crush Risk Index Calculation

The crush risk index measures **local density** in the highest-density grid cells:

```python
# From heatmap.py
# Divides floor into 10×10 grid
# Computes agents per unit area in each cell
# Returns average of top-5 highest-density cells
```

### Why This is Realistic

**Real-world evacuation scenarios:**
- People converge on exits → creates compression zones
- Faster movement + panic → increased pressure
- Exit capacity becomes limiting factor
- Crush injuries occur at exits, not in open spaces

### Example Timeline

```
BEFORE EVACUATION:
- Agents distributed across 20×20m space
- Crush risk: 1.5 (normal density)

DURING EVACUATION (first 10 seconds):
- All agents move toward 2m-wide door
- 50+ agents compress into 3m radius around exit
- Crush risk: 5.0-7.0 (HIGH - expected!)

STAGED EVACUATION ACTIVATED:
- System detects high exit compression
- Splits crowd into zones (A, B, C, D)
- Evacuates one zone at a time
- Crush risk: 3.0-4.5 (reduced but still elevated)

EVACUATION COMPLETE:
- All agents cleared
- Crush risk: 0.0
```

### System Mitigation

The coordinator implements **staged evacuation** when exit compression exceeds threshold:

1. Detects high density at exits (`exit_compression > 2.5`)
2. Activates staged mode
3. Divides crowd into zones
4. Evacuates zones sequentially
5. Reduces peak crush risk

### UI Changes

The CrushRiskGauge now shows **context-aware messages**:

**During Evacuation:**
- "Evacuation proceeding. Exit compression within expected range."
- "High exit compression expected during evacuation. System managing flow."
- "Extreme exit compression - staged evacuation in progress to manage flow."

**Normal Operations:**
- "Optimal crowd density"
- "⚠ WARNING: High local density detected"
- "🚨 CRITICAL: Crush risk - immediate action required"

## Key Takeaway

**Crush risk increasing during evacuation is CORRECT physics** - it represents real bottleneck dynamics. The system is designed to detect and mitigate this through staged evacuation.
