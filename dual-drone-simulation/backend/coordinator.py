"""
Coordinator state machine for dual-drone crowd control.
Handles normal mode (Scenarios 1 & 2) and evacuation mode (Scenario 3).
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class Status(Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"
    CRITICAL = "CRITICAL"
    EVACUATING = "EVACUATING"
    STAGED = "STAGED"
    CLEAR = "CLEAR"

class GateCommand(Enum):
    OPEN = "OPEN"
    THROTTLE = "THROTTLE"
    CLOSED = "CLOSED"

@dataclass
class ThrottleConfig:
    agents_per_batch: int
    interval_seconds: float

# Throttle configurations for different states
THROTTLE_YELLOW = ThrottleConfig(agents_per_batch=3, interval_seconds=5.0)
THROTTLE_ORANGE = ThrottleConfig(agents_per_batch=1, interval_seconds=8.0)

# Capacity thresholds
THRESHOLD_GREEN = 0.70
THRESHOLD_YELLOW = 0.85
THRESHOLD_ORANGE = 0.95
THRESHOLD_RED = 1.00

# Crush risk thresholds
CRUSH_RISK_WARNING = 4.0  # agents per unit area
CRUSH_RISK_CRITICAL = 6.0

# Evacuation thresholds
EXIT_COMPRESSION_THRESHOLD = 5.0  # triggers staged evacuation


class Coordinator:
    """
    Central coordinator managing drone states and gate commands.
    """
    
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.status = Status.GREEN
        self.gate = GateCommand.OPEN
        self.scenario = 1
        self.throttle_timer = 0.0
        self.throttle_config: Optional[ThrottleConfig] = None
        self.agents_allowed_this_batch = 0
        
        # Evacuation mode state
        self.evacuation_active = False
        self.initial_indoor_count = 0
        self.staged_evacuation = False
        self.evacuation_zone = "A"  # Current zone being evacuated
        
        # History for metrics
        self.indoor_history = []
        self.crush_risk_history = []
    
    def reset(self, scenario: int = 1, capacity: int = 100):
        """Reset coordinator for new simulation."""
        self.capacity = capacity
        self.scenario = scenario
        self.status = Status.GREEN
        self.gate = GateCommand.OPEN
        self.throttle_timer = 0.0
        self.throttle_config = None
        self.agents_allowed_this_batch = 0
        self.evacuation_active = False
        self.initial_indoor_count = 0
        self.staged_evacuation = False
        self.evacuation_zone = "A"
        self.indoor_history.clear()
        self.crush_risk_history.clear()
    
    def start_evacuation(self, current_indoor_count: int):
        """Start evacuation mode (Scenario 3)."""
        self.evacuation_active = True
        self.initial_indoor_count = current_indoor_count
        self.status = Status.EVACUATING
        self.gate = GateCommand.CLOSED
        self.staged_evacuation = False
    
    def update(self, indoor_count: int, outdoor_count: int, crush_risk: float, 
               exit_compression: float = 0.0, dt: float = 0.067) -> dict:
        """
        Update coordinator state based on current metrics.
        
        Args:
            indoor_count: Current number of agents indoors
            outdoor_count: Current number of agents in outdoor queue
            crush_risk: Current crush risk index
            exit_compression: Compression at exit points (evacuation mode)
            dt: Time step in seconds
        
        Returns:
            Dictionary with current state and commands
        """
        # Record history
        self.indoor_history.append(indoor_count)
        self.crush_risk_history.append(crush_risk)
        
        # Keep history bounded
        if len(self.indoor_history) > 300:
            self.indoor_history.pop(0)
            self.crush_risk_history.pop(0)
        
        if self.evacuation_active:
            return self._update_evacuation_mode(indoor_count, exit_compression, dt)
        else:
            return self._update_normal_mode(indoor_count, crush_risk, dt)
    
    def _update_normal_mode(self, indoor_count: int, crush_risk: float, dt: float) -> dict:
        """Update logic for Scenarios 1 & 2."""
        occupancy_ratio = indoor_count / self.capacity if self.capacity > 0 else 0
        
        # Determine status based on occupancy
        prev_status = self.status
        
        if occupancy_ratio >= THRESHOLD_RED:
            self.status = Status.CRITICAL if occupancy_ratio >= 1.0 else Status.RED
            self.gate = GateCommand.CLOSED
            self.throttle_config = None
        elif occupancy_ratio >= THRESHOLD_ORANGE:
            self.status = Status.ORANGE
            self.gate = GateCommand.THROTTLE
            self.throttle_config = THROTTLE_ORANGE
        elif occupancy_ratio >= THRESHOLD_YELLOW:
            self.status = Status.YELLOW
            self.gate = GateCommand.THROTTLE
            self.throttle_config = THROTTLE_YELLOW
        else:
            self.status = Status.GREEN
            self.gate = GateCommand.OPEN
            self.throttle_config = None
        
        # Reset throttle timer on status change
        if prev_status != self.status:
            self.throttle_timer = 0.0
            if self.throttle_config:
                self.agents_allowed_this_batch = self.throttle_config.agents_per_batch
        
        # Update throttle timer
        if self.throttle_config:
            self.throttle_timer += dt
            if self.throttle_timer >= self.throttle_config.interval_seconds:
                self.throttle_timer = 0.0
                self.agents_allowed_this_batch = self.throttle_config.agents_per_batch
        
        # Check for crush risk override
        crush_warning = crush_risk >= CRUSH_RISK_WARNING
        crush_critical = crush_risk >= CRUSH_RISK_CRITICAL
        
        return {
            "status": self.status.value,
            "gate": self.gate.value,
            "occupancy_ratio": round(occupancy_ratio, 3),
            "crush_warning": crush_warning,
            "crush_critical": crush_critical,
            "can_admit": self._can_admit_agent(),
            "throttle_timer": round(self.throttle_timer, 1) if self.throttle_config else None,
            "throttle_interval": self.throttle_config.interval_seconds if self.throttle_config else None
        }
    
    def _update_evacuation_mode(self, indoor_count: int, exit_compression: float, dt: float) -> dict:
        """Update logic for Scenario 3 evacuation."""
        evacuation_remaining = indoor_count / self.initial_indoor_count if self.initial_indoor_count > 0 else 0
        evacuation_pct = (1 - evacuation_remaining) * 100
        
        # Check for completion
        if indoor_count == 0:
            self.status = Status.CLEAR
            return {
                "status": self.status.value,
                "gate": GateCommand.CLOSED.value,
                "evacuation_pct": 100.0,
                "evacuation_complete": True,
                "staged": self.staged_evacuation
            }
        
        # Check for compression triggering staged evacuation
        if exit_compression > EXIT_COMPRESSION_THRESHOLD and not self.staged_evacuation:
            self.staged_evacuation = True
            self.status = Status.STAGED
            self.evacuation_zone = "A"
        
        return {
            "status": self.status.value,
            "gate": GateCommand.CLOSED.value,
            "evacuation_pct": round(evacuation_pct, 1),
            "evacuation_remaining": indoor_count,
            "exit_compression": round(exit_compression, 2),
            "staged": self.staged_evacuation,
            "current_zone": self.evacuation_zone if self.staged_evacuation else None,
            "evacuation_complete": False
        }
    
    def _can_admit_agent(self) -> bool:
        """Check if an agent can be admitted through the gate."""
        if self.gate == GateCommand.CLOSED:
            return False
        if self.gate == GateCommand.OPEN:
            return True
        # Throttle mode
        if self.agents_allowed_this_batch > 0:
            return True
        return False
    
    def admit_agent(self) -> bool:
        """
        Try to admit an agent. Returns True if successful.
        Decrements the batch counter in throttle mode.
        """
        if not self._can_admit_agent():
            return False
        
        if self.gate == GateCommand.THROTTLE:
            self.agents_allowed_this_batch -= 1
        
        return True
    
    def get_drone_a_status(self, indoor_count: int, crush_risk: float) -> dict:
        """Get Drone A (Indoor) status for dashboard."""
        return {
            "drone": "A",
            "role": "Indoor Monitor",
            "zone": "Building Interior",
            "monitoring": {
                "indoor_count": indoor_count,
                "capacity": self.capacity,
                "crush_risk": round(crush_risk, 2)
            },
            "status": self.status.value,
            "evacuation_mode": self.evacuation_active
        }
    
    def get_drone_b_status(self, outdoor_count: int, gate_queue: int = 0) -> dict:
        """Get Drone B (Outdoor) status for dashboard."""
        role = "Outdoor Dispersion" if self.evacuation_active else "Queue Management"
        
        return {
            "drone": "B",
            "role": role,
            "zone": "Entrance/Queue Area",
            "monitoring": {
                "outdoor_count": outdoor_count,
                "gate_queue": gate_queue
            },
            "gate_command": self.gate.value,
            "throttle_active": self.gate == GateCommand.THROTTLE,
            "evacuation_mode": self.evacuation_active
        }
    
    def get_history(self) -> list:
        """Get historical data for charts."""
        return [
            {"t": i, "count": c, "crush_risk": r} 
            for i, (c, r) in enumerate(zip(self.indoor_history, self.crush_risk_history))
        ]
