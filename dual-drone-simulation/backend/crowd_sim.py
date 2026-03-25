"""
Crowd simulation wrapper using PySocialForce.
Handles agent spawning, despawning, demographics, and environment layout.
"""
import numpy as np
import random
from typing import List, Tuple, Optional
from dataclasses import dataclass, field

# Try to import pysocialforce, fall back to mock if not available
try:
    import pysocialforce as psf
    PSF_AVAILABLE = True
except ImportError:
    PSF_AVAILABLE = False
    print("Warning: pysocialforce not installed. Using simplified physics.")

# Environment dimensions
INDOOR_WIDTH = 20
INDOOR_HEIGHT = 20
OUTDOOR_WIDTH = 20
OUTDOOR_HEIGHT = 15
DOOR_WIDTH = 2
DOOR_X = INDOOR_WIDTH / 2  # Center of building

# Door position (entrance from outdoor to indoor)
DOOR_Y = 0  # Door at y=0, indoor is y>0, outdoor is y<0

# Exit position (Scenario 1 - opposite wall)
EXIT_Y = INDOOR_HEIGHT
EXIT_X = INDOOR_WIDTH / 2

# Emergency exits (Scenario 3 - side walls)
EMERGENCY_EXIT_1 = (0, INDOOR_HEIGHT / 2)  # Left wall
EMERGENCY_EXIT_2 = (INDOOR_WIDTH, INDOOR_HEIGHT / 2)  # Right wall

# Agent demographics
SLOW_AGENT_RATIO = 0.10  # 10% elderly/mobility-impaired
NORMAL_VELOCITY = 1.2  # m/s
SLOW_VELOCITY = 0.6  # m/s


@dataclass
class Agent:
    """Represents a single agent in the simulation."""
    id: int
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    goal_x: float = 0.0
    goal_y: float = 0.0
    is_slow: bool = False
    is_panicking: bool = False
    is_indoor: bool = False
    group_id: Optional[int] = None


class CrowdSimulation:
    """
    Manages crowd simulation using PySocialForce or fallback physics.
    """
    
    def __init__(self, scenario: int = 1):
        self.scenario = scenario
        self.agents: List[Agent] = []
        self.next_agent_id = 0
        self.groups: List[List[int]] = []
        self.obstacles = self._create_obstacles()
        self.simulator = None
        self.tick = 0
        
        # Spawn configuration
        self.spawn_rate = 2.0  # agents per second
        self.spawn_timer = 0.0
        self.exit_rate = 1.5  # agents per second (Scenario 1)
        
        # Gate state (controlled by coordinator)
        self.gate_open = True
        self.holding_line_y = -3.0  # Agents wait here when gate closed
    
    def _create_obstacles(self) -> List[List[List[float]]]:
        """Create wall obstacles with door openings."""
        obstacles = []
        
        # Indoor walls
        # Bottom wall with door gap
        door_left = DOOR_X - DOOR_WIDTH / 2
        door_right = DOOR_X + DOOR_WIDTH / 2
        obstacles.append([[0, 0], [door_left, 0]])  # Left of door
        obstacles.append([[door_right, 0], [INDOOR_WIDTH, 0]])  # Right of door
        
        # Side walls
        obstacles.append([[0, 0], [0, INDOOR_HEIGHT]])  # Left wall
        obstacles.append([[INDOOR_WIDTH, 0], [INDOOR_WIDTH, INDOOR_HEIGHT]])  # Right wall
        
        # Top wall (with exit for Scenario 1)
        if self.scenario == 1:
            exit_left = EXIT_X - DOOR_WIDTH / 2
            exit_right = EXIT_X + DOOR_WIDTH / 2
            obstacles.append([[0, INDOOR_HEIGHT], [exit_left, INDOOR_HEIGHT]])
            obstacles.append([[exit_right, INDOOR_HEIGHT], [INDOOR_WIDTH, INDOOR_HEIGHT]])
        else:
            obstacles.append([[0, INDOOR_HEIGHT], [INDOOR_WIDTH, INDOOR_HEIGHT]])
        
        # Emergency exits for Scenario 3 (modify side walls)
        if self.scenario == 3:
            # Will be handled differently - side wall gaps
            pass
        
        return obstacles
    
    def reset(self, scenario: int = 1):
        """Reset simulation state."""
        self.scenario = scenario
        self.agents.clear()
        self.groups.clear()
        self.next_agent_id = 0
        self.tick = 0
        self.spawn_timer = 0.0
        self.obstacles = self._create_obstacles()
        self.simulator = None
        self.gate_open = True
    
    def spawn_agent(self, x: float, y: float, goal_x: float, goal_y: float, 
                    is_slow: bool = False, group_id: Optional[int] = None) -> Agent:
        """Spawn a new agent at the specified position."""
        agent = Agent(
            id=self.next_agent_id,
            x=x,
            y=y,
            goal_x=goal_x,
            goal_y=goal_y,
            is_slow=is_slow,
            is_indoor=(y >= 0),
            group_id=group_id
        )
        self.next_agent_id += 1
        self.agents.append(agent)
        return agent
    
    def spawn_outdoor_agent(self) -> Optional[Agent]:
        """Spawn an agent in the outdoor queue area."""
        # Random position in outdoor zone
        x = random.uniform(DOOR_X - 5, DOOR_X + 5)
        y = random.uniform(-OUTDOOR_HEIGHT + 2, -2)
        
        # Goal is the door
        goal_x = DOOR_X
        goal_y = 1.0  # Just inside the door
        
        # 10% chance of being slow
        is_slow = random.random() < SLOW_AGENT_RATIO
        
        return self.spawn_agent(x, y, goal_x, goal_y, is_slow)
    
    def spawn_initial_crowd(self, indoor_count: int = 20, outdoor_count: int = 10):
        """Spawn initial crowd for simulation start."""
        # Indoor agents
        for _ in range(indoor_count):
            x = random.uniform(2, INDOOR_WIDTH - 2)
            y = random.uniform(2, INDOOR_HEIGHT - 2)
            
            if self.scenario == 1:
                # Goal is exit
                goal_x = EXIT_X
                goal_y = INDOOR_HEIGHT + 1
            else:
                # Random wandering goal
                goal_x = random.uniform(2, INDOOR_WIDTH - 2)
                goal_y = random.uniform(2, INDOOR_HEIGHT - 2)
            
            is_slow = random.random() < SLOW_AGENT_RATIO
            agent = self.spawn_agent(x, y, goal_x, goal_y, is_slow)
            agent.is_indoor = True
        
        # Outdoor agents
        for _ in range(outdoor_count):
            self.spawn_outdoor_agent()
    
    def _build_state_array(self) -> np.ndarray:
        """Build numpy state array for PySocialForce."""
        if not self.agents:
            return np.array([]).reshape(0, 6)
        
        states = []
        for agent in self.agents:
            vel = SLOW_VELOCITY if agent.is_slow else NORMAL_VELOCITY
            # Compute velocity direction towards goal
            dx = agent.goal_x - agent.x
            dy = agent.goal_y - agent.y
            dist = np.sqrt(dx**2 + dy**2)
            if dist > 0.1:
                vx = (dx / dist) * vel * 0.5  # Initial velocity towards goal
                vy = (dy / dist) * vel * 0.5
            else:
                vx, vy = 0, 0
            
            states.append([agent.x, agent.y, vx, vy, agent.goal_x, agent.goal_y])
        
        return np.array(states)
    
    def _update_agents_from_state(self, states: np.ndarray):
        """Update agent positions from simulation state."""
        for i, agent in enumerate(self.agents):
            if i < len(states):
                agent.x = float(states[i, 0])
                agent.y = float(states[i, 1])
                agent.vx = float(states[i, 2])
                agent.vy = float(states[i, 3])
                agent.is_indoor = agent.y >= 0
    
    def step(self, dt: float = 0.067, gate_open: bool = True):
        """
        Advance simulation by one time step.
        
        Args:
            dt: Time step in seconds (~15 FPS = 0.067s)
            gate_open: Whether the gate is open for entry
        """
        self.tick += 1
        self.gate_open = gate_open
        
        # Spawn new outdoor agents
        self.spawn_timer += dt
        if self.spawn_timer >= 1.0 / self.spawn_rate:
            self.spawn_timer = 0.0
            if len([a for a in self.agents if not a.is_indoor]) < 50:  # Cap outdoor
                self.spawn_outdoor_agent()
        
        if not self.agents:
            return
        
        # Build state array
        state_array = self._build_state_array()
        
        if PSF_AVAILABLE and len(self.agents) > 0:
            # Use PySocialForce
            try:
                self.simulator = psf.Simulator(
                    state_array,
                    groups=self._build_groups(),
                    obstacles=self.obstacles
                )
                self.simulator.step(1)
                new_states, _ = self.simulator.get_states()
                if len(new_states) > 0:
                    self._update_agents_from_state(new_states[-1])
            except Exception as e:
                # Fallback to simple physics
                self._simple_physics_step(dt)
        else:
            # Simple physics fallback
            self._simple_physics_step(dt)
        
        # Handle gate logic - stop agents at holding line if gate closed
        if not gate_open:
            for agent in self.agents:
                if not agent.is_indoor and agent.y > self.holding_line_y:
                    agent.y = self.holding_line_y
                    agent.vy = 0
        
        # Handle transitions through door
        self._handle_door_transitions()
        
        # Handle exits (Scenario 1)
        if self.scenario == 1:
            self._handle_exits()
        
        # Update goals for wandering agents (Scenario 2)
        if self.scenario == 2:
            self._update_wandering_goals()
    
    def _simple_physics_step(self, dt: float):
        """Simple physics when PySocialForce not available."""
        for agent in self.agents:
            # Move towards goal
            dx = agent.goal_x - agent.x
            dy = agent.goal_y - agent.y
            dist = np.sqrt(dx**2 + dy**2)
            
            vel = SLOW_VELOCITY if agent.is_slow else NORMAL_VELOCITY
            
            if dist > 0.5:
                agent.vx = (dx / dist) * vel
                agent.vy = (dy / dist) * vel
            else:
                agent.vx = 0
                agent.vy = 0
            
            # Apply velocity
            new_x = agent.x + agent.vx * dt
            new_y = agent.y + agent.vy * dt
            
            # Simple boundary collision
            if agent.is_indoor:
                new_x = np.clip(new_x, 0.5, INDOOR_WIDTH - 0.5)
                new_y = np.clip(new_y, 0.5, INDOOR_HEIGHT - 0.5)
            
            agent.x = new_x
            agent.y = new_y
            agent.is_indoor = agent.y >= 0
    
    def _build_groups(self) -> List[List[int]]:
        """Build group list for PySocialForce."""
        groups_dict = {}
        for i, agent in enumerate(self.agents):
            if agent.group_id is not None:
                if agent.group_id not in groups_dict:
                    groups_dict[agent.group_id] = []
                groups_dict[agent.group_id].append(i)
        return list(groups_dict.values())
    
    def _handle_door_transitions(self):
        """Handle agents moving through the door."""
        door_left = DOOR_X - DOOR_WIDTH / 2
        door_right = DOOR_X + DOOR_WIDTH / 2
        
        for agent in self.agents:
            # Check if near door
            if door_left <= agent.x <= door_right:
                if not agent.is_indoor and agent.y >= -0.5 and self.gate_open:
                    # Transition to indoor
                    agent.is_indoor = True
                    agent.y = max(agent.y, 1.0)
                    
                    # Set new goal based on scenario
                    if self.scenario == 1:
                        agent.goal_x = EXIT_X
                        agent.goal_y = INDOOR_HEIGHT + 1
                    else:
                        agent.goal_x = random.uniform(3, INDOOR_WIDTH - 3)
                        agent.goal_y = random.uniform(3, INDOOR_HEIGHT - 3)
    
    def _handle_exits(self):
        """Handle agents exiting (Scenario 1)."""
        exit_left = EXIT_X - DOOR_WIDTH / 2
        exit_right = EXIT_X + DOOR_WIDTH / 2
        
        to_remove = []
        for agent in self.agents:
            if agent.is_indoor and agent.y >= INDOOR_HEIGHT - 0.5:
                if exit_left <= agent.x <= exit_right:
                    to_remove.append(agent)
        
        for agent in to_remove:
            self.agents.remove(agent)
    
    def _update_wandering_goals(self):
        """Update goals for wandering agents (Scenario 2)."""
        for agent in self.agents:
            if agent.is_indoor:
                # Check if reached goal
                dist = np.sqrt((agent.x - agent.goal_x)**2 + (agent.y - agent.goal_y)**2)
                if dist < 1.0:
                    # New random goal
                    agent.goal_x = random.uniform(3, INDOOR_WIDTH - 3)
                    agent.goal_y = random.uniform(3, INDOOR_HEIGHT - 3)
    
    def start_evacuation(self):
        """Start evacuation mode (Scenario 3)."""
        self.scenario = 3
        self.gate_open = False
        
        # Set all indoor agents to exit goals
        for agent in self.agents:
            if agent.is_indoor:
                # Assign to nearest exit
                dist_main = agent.y  # Distance to main door (y=0)
                dist_left = np.sqrt(agent.x**2 + (agent.y - INDOOR_HEIGHT/2)**2)
                dist_right = np.sqrt((agent.x - INDOOR_WIDTH)**2 + (agent.y - INDOOR_HEIGHT/2)**2)
                
                min_dist = min(dist_main, dist_left, dist_right)
                
                if min_dist == dist_main:
                    agent.goal_x = DOOR_X
                    agent.goal_y = -1
                elif min_dist == dist_left:
                    agent.goal_x = -1
                    agent.goal_y = INDOOR_HEIGHT / 2
                else:
                    agent.goal_x = INDOOR_WIDTH + 1
                    agent.goal_y = INDOOR_HEIGHT / 2
    
    def get_indoor_agents(self) -> List[Agent]:
        """Get list of indoor agents."""
        return [a for a in self.agents if a.is_indoor]
    
    def get_outdoor_agents(self) -> List[Agent]:
        """Get list of outdoor agents."""
        return [a for a in self.agents if not a.is_indoor]
    
    def get_agent_positions(self, indoor_only: bool = False) -> List[List[float]]:
        """Get agent positions as list of [x, y]."""
        agents = self.get_indoor_agents() if indoor_only else self.agents
        return [[a.x, a.y] for a in agents]
    
    def get_state_for_broadcast(self) -> List[List]:
        """Get agent state for WebSocket broadcast."""
        return [
            [
                round(a.x, 2),
                round(a.y, 2),
                round(a.vx, 2),
                round(a.vy, 2),
                1 if a.is_slow else 0,
                1 if a.is_panicking else 0
            ]
            for a in self.agents
        ]
