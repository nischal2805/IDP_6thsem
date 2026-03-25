"""
Panic propagation model for crowd simulation.
Implements spreading panic behavior with decay.
"""
import numpy as np
import random
from typing import List, Set

# Panic configuration
PANIC_SPEED_THRESHOLD = 2.0  # Speed above which agent is considered panicking
PANIC_PROPAGATION_RADIUS = 3.0  # Radius for panic spread
PANIC_PROPAGATION_PROBABILITY = 0.15  # Probability of panic spreading per tick
PANIC_VELOCITY_MULTIPLIER = 2.5  # How much faster panicking agents move
PANIC_DECAY_TIME = 8.0  # Seconds before panic decays
MAX_PANIC_VELOCITY = 3.5  # Cap to prevent tunneling through walls


class PanicManager:
    """Manages panic state and propagation for all agents."""
    
    def __init__(self):
        self.panic_flags: dict = {}  # agent_id -> is_panicking
        self.panic_timers: dict = {}  # agent_id -> time_since_last_trigger
        self.panic_source: tuple = None  # (x, y) of injection point
    
    def reset(self):
        """Reset all panic states."""
        self.panic_flags.clear()
        self.panic_timers.clear()
        self.panic_source = None
    
    def inject_panic(self, x: float, y: float, agent_states: np.ndarray, radius: float = 5.0):
        """
        Inject panic at a specific location, affecting nearby agents.
        
        Args:
            x, y: Center of panic injection
            agent_states: Array of agent states [x, y, vx, vy, goal_x, goal_y]
            radius: Radius of initial panic zone
        """
        self.panic_source = (x, y)
        
        for i, agent in enumerate(agent_states):
            ax, ay = agent[0], agent[1]
            dist = np.sqrt((ax - x)**2 + (ay - y)**2)
            if dist < radius:
                self.panic_flags[i] = True
                self.panic_timers[i] = 0.0
    
    def propagate_panic(self, agent_states: np.ndarray, dt: float) -> Set[int]:
        """
        Propagate panic to nearby agents and handle decay.
        
        Args:
            agent_states: Current agent states
            dt: Time step in seconds
        
        Returns:
            Set of currently panicking agent indices
        """
        num_agents = len(agent_states)
        
        # Initialize flags for new agents
        for i in range(num_agents):
            if i not in self.panic_flags:
                self.panic_flags[i] = False
                self.panic_timers[i] = PANIC_DECAY_TIME + 1
        
        # Check speed-based panic triggers
        for i, agent in enumerate(agent_states):
            speed = np.sqrt(agent[2]**2 + agent[3]**2)
            if speed > PANIC_SPEED_THRESHOLD:
                self.panic_flags[i] = True
                self.panic_timers[i] = 0.0
        
        # Propagate panic to neighbors
        new_panic = set()
        panicking_agents = [i for i, p in self.panic_flags.items() if p and i < num_agents]
        
        for i in panicking_agents:
            if i >= num_agents:
                continue
            agent = agent_states[i]
            ax, ay = agent[0], agent[1]
            
            for j, other in enumerate(agent_states):
                if j == i or self.panic_flags.get(j, False):
                    continue
                
                ox, oy = other[0], other[1]
                dist = np.sqrt((ax - ox)**2 + (ay - oy)**2)
                
                if dist < PANIC_PROPAGATION_RADIUS:
                    if random.random() < PANIC_PROPAGATION_PROBABILITY:
                        new_panic.add(j)
        
        # Apply new panic
        for j in new_panic:
            self.panic_flags[j] = True
            self.panic_timers[j] = 0.0
        
        # Update timers and decay
        for i in list(self.panic_flags.keys()):
            if i >= num_agents:
                del self.panic_flags[i]
                del self.panic_timers[i]
                continue
            
            if self.panic_flags[i]:
                self.panic_timers[i] += dt
                if self.panic_timers[i] > PANIC_DECAY_TIME:
                    self.panic_flags[i] = False
        
        return {i for i, p in self.panic_flags.items() if p and i < num_agents}
    
    def modify_agent_behavior(self, agent_states: np.ndarray, panicking_indices: Set[int]) -> np.ndarray:
        """
        Modify velocities of panicking agents.
        
        Args:
            agent_states: Current agent states
            panicking_indices: Set of panicking agent indices
        
        Returns:
            Modified agent states
        """
        modified_states = agent_states.copy()
        
        for i in panicking_indices:
            if i >= len(modified_states):
                continue
            
            # Increase desired velocity (will be reflected in next simulation step)
            vx, vy = modified_states[i, 2], modified_states[i, 3]
            speed = np.sqrt(vx**2 + vy**2)
            
            if speed > 0.01:
                # Scale up velocity but cap at max
                new_speed = min(speed * PANIC_VELOCITY_MULTIPLIER, MAX_PANIC_VELOCITY)
                scale = new_speed / speed
                modified_states[i, 2] = vx * scale
                modified_states[i, 3] = vy * scale
            
            # Occasionally randomize goal for panicking agents (10% chance per tick)
            if random.random() < 0.1:
                # Random goal within bounds
                modified_states[i, 4] = random.uniform(2, 18)
                modified_states[i, 5] = random.uniform(2, 18)
        
        return modified_states
    
    def get_panic_state(self) -> dict:
        """Get current panic state for serialization."""
        return {
            "active_panic_count": sum(1 for p in self.panic_flags.values() if p),
            "panic_source": self.panic_source,
            "panicking_agents": [i for i, p in self.panic_flags.items() if p]
        }
