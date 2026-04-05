"""
Scenario configurations for crowd simulation.
Defines all available scenarios with their parameters.
"""

SCENARIOS = {
    1: {
        "id": 1,
        "name": "Entry + Exit (Basic Flow)",
        "description": "Steady state with agents entering and exiting. Tests normal operations.",
        "type": "basic",
        "has_exit": True,
        "has_zones": False,
        "icon": "↔️"
    },
    2: {
        "id": 2,
        "name": "Entry Only (Capacity Test)",
        "description": "No exit - tests capacity limits and gate closure behavior.",
        "type": "basic",
        "has_exit": False,
        "has_zones": False,
        "icon": "➡️"
    },
    3: {
        "id": 3,
        "name": "Emergency Evacuation",
        "description": "All agents evacuate through exits. Tests crush compression at exits.",
        "type": "evacuation",
        "has_exit": True,
        "has_zones": False,
        "icon": "🚨"
    },
    4: {
        "id": 4,
        "name": "Stadium Stands (Realistic)",
        "description": "Main entry with 3 stands (A/B/C), seat assignment, and per-stand gate closure when full.",
        "type": "stadium",
        "has_exit": False,
        "has_zones": True,
        "zone_type": "stadium",
        "icon": "🏟️"
    },
    5: {
        "id": 5,
        "name": "Multi-Lane Queue",
        "description": "4 parallel entry lanes with automatic load balancing.",
        "type": "multi_lane",
        "has_exit": True,
        "has_zones": True,
        "zone_type": "multi_lane",
        "icon": "🚦"
    },
    6: {
        "id": 6,
        "name": "Tiered Admission (VIP/General/Student)",
        "description": "Priority-based admission with separate lanes for different tiers.",
        "type": "tiered",
        "has_exit": True,
        "has_zones": True,
        "zone_type": "tiered",
        "icon": "🎫"
    },
    7: {
        "id": 7,
        "name": "Bidirectional Flow",
        "description": "Agents entering and exiting through same corridor. Tests counter-flow.",
        "type": "bidirectional",
        "has_exit": True,
        "has_zones": True,
        "zone_type": "bidirectional",
        "icon": "⇄"
    },
    8: {
        "id": 8,
        "name": "Predictive Flow Control",
        "description": "AI predicts congestion and pre-emptively activates throttling.",
        "type": "predictive",
        "has_exit": True,
        "has_zones": False,
        "icon": "🔮"
    }
}


def get_scenario(scenario_id: int):
    """Get scenario configuration by ID."""
    return SCENARIOS.get(scenario_id, SCENARIOS[1])


def get_all_scenarios():
    """Get all scenario configurations."""
    return list(SCENARIOS.values())
