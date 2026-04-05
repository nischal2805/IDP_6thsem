"""
Multi-zone management system for enhanced scenarios.
Supports stadium sections, multi-lane queues, and tiered admission.
"""
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import random


@dataclass
class Zone:
    """Represents a zone/section in the simulation."""
    id: str
    name: str
    capacity: int
    position: Tuple[float, float]  # (x, y) center
    size: Tuple[float, float]      # (width, height)
    current_count: int = 0
    redirect_target: Optional[str] = None
    priority: int = 2  # 1=VIP, 2=General, 3=Student
    active: bool = True
    
    def is_full(self) -> bool:
        return self.current_count >= self.capacity
    
    def needs_redirection(self, threshold: float = 0.8) -> bool:
        return self.current_count >= self.capacity * threshold
    
    def contains_point(self, x: float, y: float) -> bool:
        """Check if a point is within this zone."""
        x_min = self.position[0] - self.size[0] / 2
        x_max = self.position[0] + self.size[0] / 2
        y_min = self.position[1] - self.size[1] / 2
        y_max = self.position[1] + self.size[1] / 2
        return x_min <= x <= x_max and y_min <= y <= y_max


@dataclass
class Lane:
    """Represents an entry/exit lane."""
    id: int
    position: Tuple[float, float]
    queue_size: int = 0
    active: bool = True
    throughput_rate: float = 2.0  # agents per second
    
    def is_congested(self, threshold: int = 15) -> bool:
        return self.queue_size > threshold


class MultiZoneManager:
    """Manages multiple zones for complex scenarios."""
    
    def __init__(self, scenario_type: str = "basic"):
        self.zones: Dict[str, Zone] = {}
        self.lanes: Dict[int, Lane] = {}
        self.scenario_type = scenario_type
        self.redirection_threshold = 0.8
        self.initialize_scenario(scenario_type)
    
    def initialize_scenario(self, scenario_type: str):
        """Initialize zones based on scenario type."""
        self.zones.clear()
        self.lanes.clear()
        
        if scenario_type == "stadium":
            self._init_stadium_sections()
        elif scenario_type == "multi_lane":
            self._init_multi_lane()
        elif scenario_type == "tiered":
            self._init_tiered_admission()
        elif scenario_type == "bidirectional":
            self._init_bidirectional()
    
    def _init_stadium_sections(self):
        """Stadium with 3 stands (A, B, C) aligned with crowd_sim layout."""
        sections = [
            ("left", "Stand A (Left)", (3, 14), (6, 12), 40),
            ("center", "Stand B (Center)", (10, 16), (6, 8), 50),
            ("right", "Stand C (Right)", (17, 14), (6, 12), 40),
        ]

        for zone_id, name, pos, size, cap in sections:
            self.zones[zone_id] = Zone(
                id=zone_id,
                name=name,
                capacity=cap,
                position=pos,
                size=size,
                redirect_target=None
            )

        # Redirect chain across stands as they near capacity.
        self.zones["left"].redirect_target = "center"
        self.zones["center"].redirect_target = "right"
    
    def _init_multi_lane(self):
        """Multiple entry lanes with load balancing."""
        lane_positions = [
            (8, -2),
            (10, -2),
            (12, -2),
            (14, -2)
        ]
        
        for i, pos in enumerate(lane_positions, start=1):
            self.lanes[i] = Lane(
                id=i,
                position=pos,
                active=(i <= 2)  # Start with 2 lanes active
            )
        
        # Create holding zones for each lane
        for i, pos in enumerate(lane_positions, start=1):
            self.zones[f"lane_{i}"] = Zone(
                id=f"lane_{i}",
                name=f"Lane {i}",
                capacity=20,
                position=pos,
                size=(1.5, 3)
            )
    
    def _init_tiered_admission(self):
        """VIP, General, and Student lanes."""
        tiers = [
            ("vip", "VIP Lane", (8, -2), 20, 1),
            ("general", "General Lane", (10, -2), 100, 2),
            ("student", "Student Lane", (12, -2), 50, 3)
        ]
        
        for zone_id, name, pos, cap, priority in tiers:
            self.zones[zone_id] = Zone(
                id=zone_id,
                name=name,
                capacity=cap,
                position=pos,
                size=(1.5, 4),
                priority=priority
            )
    
    def _init_bidirectional(self):
        """Bidirectional corridor zones."""
        # Create zones for inflow and outflow
        self.zones["in"] = Zone(
            id="in",
            name="Entry Flow",
            capacity=30,
            position=(10, 5),
            size=(4, 10)
        )
        
        self.zones["out"] = Zone(
            id="out",
            name="Exit Flow",
            capacity=30,
            position=(10, 15),
            size=(4, 10)
        )
    
    def assign_agent_to_zone(self, agent_type: str = "general") -> Optional[Zone]:
        """Assign an agent to the best available zone."""
        if not self.zones:
            return None
        
        # Filter zones by priority if tiered scenario
        if self.scenario_type == "tiered":
            priority_map = {"vip": 1, "general": 2, "student": 3}
            target_priority = priority_map.get(agent_type, 2)
            available = [z for z in self.zones.values() 
                        if z.priority == target_priority and z.active and not z.is_full()]
        else:
            available = [z for z in self.zones.values() 
                        if z.active and not z.is_full()]
        
        if not available:
            # All zones full, find least full zone
            available = sorted(self.zones.values(), 
                             key=lambda z: z.current_count / z.capacity)[:1]
        
        return available[0] if available else None
    
    def check_redirection(self, zone_id: str) -> Optional[str]:
        """Check if zone needs redirection and return target zone."""
        if zone_id not in self.zones:
            return None
        
        zone = self.zones[zone_id]
        if zone.needs_redirection(self.redirection_threshold):
            if zone.redirect_target and zone.redirect_target in self.zones:
                target = self.zones[zone.redirect_target]
                if not target.is_full():
                    return zone.redirect_target
        
        return None
    
    def get_least_congested_lane(self) -> Optional[Lane]:
        """Get the lane with smallest queue."""
        active_lanes = [l for l in self.lanes.values() if l.active]
        if not active_lanes:
            return None
        return min(active_lanes, key=lambda l: l.queue_size)
    
    def balance_lanes(self):
        """Auto-activate lanes when congestion detected."""
        active_lanes = [l for l in self.lanes.values() if l.active]
        inactive_lanes = [l for l in self.lanes.values() if not l.active]
        
        if not active_lanes or not inactive_lanes:
            return
        
        max_queue = max(l.queue_size for l in active_lanes)
        
        # Activate new lane if max queue > 15
        if max_queue > 15 and inactive_lanes:
            inactive_lanes[0].active = True
        
        # Deactivate lane if all queues < 5
        if len(active_lanes) > 1 and max_queue < 5:
            # Close the emptiest lane
            min_lane = min(active_lanes, key=lambda l: l.queue_size)
            if min_lane.queue_size == 0:
                min_lane.active = False
    
    def update_zone_counts(self, agents: List) -> Dict[str, int]:
        """Update agent counts per zone based on positions."""
        # Reset counts
        for zone in self.zones.values():
            zone.current_count = 0
        
        # Count agents in each zone
        zone_counts = {z_id: 0 for z_id in self.zones.keys()}
        
        for agent in agents:
            x, y = agent.x, agent.y
            for zone_id, zone in self.zones.items():
                if zone.contains_point(x, y):
                    zone.current_count += 1
                    zone_counts[zone_id] += 1
                    break
        
        return zone_counts
    
    def get_zone_stats(self) -> List[Dict]:
        """Get statistics for all zones."""
        return [
            {
                "id": z.id,
                "name": z.name,
                "current": z.current_count,
                "capacity": z.capacity,
                "utilization": round(z.current_count / z.capacity * 100, 1) if z.capacity > 0 else 0,
                "status": "FULL" if z.is_full() else "WARNING" if z.needs_redirection() else "NORMAL",
                "active": z.active,
                "position": z.position,
                "size": z.size
            }
            for z in self.zones.values()
        ]
    
    def get_lane_stats(self) -> List[Dict]:
        """Get statistics for all lanes."""
        return [
            {
                "id": l.id,
                "queue_size": l.queue_size,
                "active": l.active,
                "congested": l.is_congested(),
                "position": l.position
            }
            for l in self.lanes.values()
        ]
