"""
Crowd simulation wrapper using PySocialForce.
Handles agent spawning, despawning, demographics, and environment layout.
Implements realistic crowd behavior with state machines and environment awareness.
"""
import numpy as np
import random
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field
from enum import Enum
from scenarios import get_scenario

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

# Environment awareness thresholds
DENSITY_SLOWDOWN_THRESHOLD = 2.0  # people per m² - start slowing down
DENSITY_STOP_THRESHOLD = 4.0      # people per m² - stop/shuffle
COMFORT_ZONE_RADIUS = 1.5         # meters - personal space
AWARENESS_RADIUS = 3.0            # meters - how far agents "see"


class AgentState(Enum):
    """Behavioral states for realistic crowd behavior."""
    QUEUING = "queuing"           # Waiting in outdoor queue
    WALKING = "walking"           # Moving toward goal
    ENTERING = "entering"         # Passing through gate/door
    FINDING_SEAT = "finding_seat" # Looking for seat in stadium
    SEATED = "seated"             # Sitting in seat (stationary)
    EVACUATING = "evacuating"     # Emergency exit mode
    WANDERING = "wandering"       # Random movement (no specific goal)


@dataclass
class Agent:
    """Represents a single agent in the simulation with behavioral state."""
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
    
    # Behavioral state
    state: AgentState = AgentState.WALKING
    assigned_stand: Optional[str] = None  # For stadium: "left", "center", "right"
    seat_position: Optional[Tuple[float, float]] = None  # Assigned seat
    
    # Environment awareness
    local_density: float = 0.0            # People per m² around agent
    speed_modifier: float = 1.0           # Density-based speed adjustment
    patience: float = 1.0                 # How long willing to wait (0-1)
    time_in_state: float = 0.0            # Time spent in current state


class CrowdSimulation:
    """
    Manages crowd simulation using PySocialForce or fallback physics.
    Implements realistic crowd behavior with environment awareness.
    """
    
    def __init__(self, scenario: int = 1):
        self.scenario = scenario
        self.scenario_config = get_scenario(scenario)
        self.agents: List[Agent] = []
        self.next_agent_id = 0
        self.groups: List[List[int]] = []
        self.obstacles = self._create_obstacles()
        self.simulator = None
        self.tick = 0
        
        # Spawn configuration (scenario-dependent)
        self.spawn_rate = self._get_spawn_rate()
        self.spawn_timer = 0.0
        self.exit_rate = 1.5  # agents per second (Scenario 1)
        
        # Gate state (controlled by coordinator)
        self.gate_open = True
        self.holding_line_y = -3.0  # Agents wait here when gate closed
        
        # Bidirectional flow control (Scenario 7)
        self.bidirectional_mode = "entry"  # "entry" or "exit"
        self.bidirectional_timer = 0.0
        self.bidirectional_interval = 10.0  # Switch every 10 seconds
        
        # Stadium configuration (Scenario 4 - enhanced)
        self.stadium_stands = self._init_stadium_stands()
        self.stand_gates: Dict[str, bool] = {"left": True, "center": True, "right": True}
        self.seats: Dict[str, List[Tuple[float, float, bool]]] = {}  # (x, y, occupied)
        if self.scenario_config.get("type") == "stadium":
            self._init_stadium_seats()
    
    def _init_stadium_stands(self) -> Dict:
        """Initialize stadium stand layout with 3 stands."""
        return {
            "left": {
                "name": "Stand A (Left)",
                "bounds": {"x_min": 0, "x_max": 6, "y_min": 8, "y_max": 20},
                "entrance": (3, 7),
                "capacity": 40,
                "current": 0,
                "gate_open": True
            },
            "center": {
                "name": "Stand B (Center)",
                "bounds": {"x_min": 7, "x_max": 13, "y_min": 12, "y_max": 20},
                "entrance": (10, 11),
                "capacity": 50,
                "current": 0,
                "gate_open": True
            },
            "right": {
                "name": "Stand C (Right)",
                "bounds": {"x_min": 14, "x_max": 20, "y_min": 8, "y_max": 20},
                "entrance": (17, 7),
                "capacity": 40,
                "current": 0,
                "gate_open": True
            }
        }
    
    def _init_stadium_seats(self):
        """Generate seat positions for each stadium stand."""
        for stand_id, stand in self.stadium_stands.items():
            bounds = stand["bounds"]
            seats = []
            
            # Generate seat grid - rows of seats
            x_min, x_max = bounds["x_min"] + 0.5, bounds["x_max"] - 0.5
            y_min, y_max = bounds["y_min"] + 0.5, bounds["y_max"] - 0.5
            
            # Seat spacing
            row_spacing = 1.2
            seat_spacing = 1.0
            
            y = y_min + 0.5
            while y < y_max:
                x = x_min + 0.5
                while x < x_max:
                    seats.append((x, y, False))  # x, y, occupied
                    x += seat_spacing
                y += row_spacing
            
            self.seats[stand_id] = seats
            stand["capacity"] = len(seats)
    
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
    
    def _get_spawn_rate(self) -> float:
        """Get scenario-specific spawn rate."""
        scenario_type = self.scenario_config.get("type")
        
        if scenario_type == "evacuation":
            return 0.0  # No new spawns during evacuation
        elif scenario_type == "multi_lane":
            return 4.0  # Higher rate for multi-lane
        elif scenario_type == "tiered":
            return 2.5  # Moderate for tiered admission
        elif self.scenario == 2:  # Entry Only
            return 3.0  # Higher rate to show capacity filling
        elif scenario_type == "bidirectional":
            return 1.5  # Lower rate for bidirectional flow
        else:
            return 2.0  # Default rate
    
    def reset(self, scenario: int = 1):
        """Reset simulation state."""
        self.scenario = scenario
        self.scenario_config = get_scenario(scenario)
        self.agents.clear()
        self.groups.clear()
        self.next_agent_id = 0
        self.tick = 0
        self.spawn_timer = 0.0
        self.spawn_rate = self._get_spawn_rate()
        self.obstacles = self._create_obstacles()
        self.simulator = None
        self.gate_open = True
        self.bidirectional_mode = "entry"
        self.bidirectional_timer = 0.0
        
        # Reset stadium state
        self.stadium_stands = self._init_stadium_stands()
        self.stand_gates = {"left": True, "center": True, "right": True}
        self.seats = {}
        if self.scenario_config.get("type") == "stadium":
            self._init_stadium_seats()
    
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
        scenario_type = self.scenario_config.get("type")
        
        # Scenario 7: Bidirectional - only spawn in entry mode
        if scenario_type == "bidirectional" and self.bidirectional_mode != "entry":
            return None
        
        # Random position in outdoor zone
        if scenario_type == "multi_lane":
            # Spawn in one of 4 lanes
            lane = random.randint(0, 3)
            x = DOOR_X - 6 + lane * 4
            y = random.uniform(-OUTDOOR_HEIGHT + 2, -2)
        else:
            x = random.uniform(DOOR_X - 5, DOOR_X + 5)
            y = random.uniform(-OUTDOOR_HEIGHT + 2, -2)
        
        # Goal is the door
        goal_x = DOOR_X
        goal_y = 1.0  # Just inside the door
        
        # 10% chance of being slow (except for tiered scenario)
        if scenario_type == "tiered":
            # 20% VIP, 60% General, 20% Student
            tier = random.choices(["vip", "general", "student"], weights=[0.2, 0.6, 0.2])[0]
            is_slow = tier == "student"
        else:
            is_slow = random.random() < SLOW_AGENT_RATIO
        
        return self.spawn_agent(x, y, goal_x, goal_y, is_slow)
    
    def spawn_initial_crowd(self, indoor_count: int = 20, outdoor_count: int = 10):
        """Spawn initial crowd for simulation start."""
        scenario_type = self.scenario_config.get("type")
        
        # Adjust initial counts based on scenario
        if scenario_type == "evacuation":
            indoor_count = 50  # More people for evacuation
            outdoor_count = 0
        elif self.scenario == 2:  # Entry Only
            indoor_count = 10  # Start with fewer, will fill up
            outdoor_count = 15
        elif scenario_type == "bidirectional":
            indoor_count = 30  # More indoor agents to exit
            outdoor_count = 10
        
        # Indoor agents
        for _ in range(indoor_count):
            x = random.uniform(2, INDOOR_WIDTH - 2)
            y = random.uniform(2, INDOOR_HEIGHT - 2)
            
            goal_x, goal_y = self._get_initial_indoor_goal(scenario_type)
            
            is_slow = random.random() < SLOW_AGENT_RATIO
            agent = self.spawn_agent(x, y, goal_x, goal_y, is_slow)
            agent.is_indoor = True
        
        # Outdoor agents
        for _ in range(outdoor_count):
            self.spawn_outdoor_agent()
    
    def _get_initial_indoor_goal(self, scenario_type: str) -> Tuple[float, float]:
        """Get initial goal for indoor agents based on scenario."""
        if scenario_type == "basic" and self.scenario_config.get("has_exit"):
            # Scenario 1: Exit through top
            return EXIT_X, INDOOR_HEIGHT + 1
        elif scenario_type == "evacuation":
            # Will be set by start_evacuation()
            return EXIT_X, INDOOR_HEIGHT + 1
        elif scenario_type == "bidirectional":
            # Exit through door (bottom)
            return DOOR_X, -1
        else:
            # Random wandering
            return random.uniform(3, INDOOR_WIDTH - 3), random.uniform(3, INDOOR_HEIGHT - 3)
    
    def _build_state_array(self) -> np.ndarray:
        """Build numpy state array for PySocialForce."""
        if not self.agents:
            return np.array([]).reshape(0, 6)
        
        states = []
        for agent in self.agents:
            vel = SLOW_VELOCITY if agent.is_slow else NORMAL_VELOCITY
            # Apply density-based speed modifier
            vel *= agent.speed_modifier
            
            # Seated agents don't move
            if agent.state == AgentState.SEATED:
                states.append([agent.x, agent.y, 0, 0, agent.x, agent.y])
                continue
            
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
    
    def _compute_local_densities(self):
        """Compute local density around each agent for environment-aware behavior."""
        if len(self.agents) < 2:
            for agent in self.agents:
                agent.local_density = 0.0
                agent.speed_modifier = 1.0
            return
        
        positions = np.array([[a.x, a.y] for a in self.agents])
        
        for i, agent in enumerate(self.agents):
            # Count neighbors within awareness radius
            distances = np.sqrt(np.sum((positions - positions[i])**2, axis=1))
            neighbors_in_radius = np.sum((distances > 0) & (distances < AWARENESS_RADIUS))
            
            # Calculate local density (people per m² in awareness circle)
            area = np.pi * AWARENESS_RADIUS**2
            agent.local_density = neighbors_in_radius / area
            
            # Compute speed modifier based on density
            if agent.local_density < DENSITY_SLOWDOWN_THRESHOLD:
                agent.speed_modifier = 1.0
            elif agent.local_density < DENSITY_STOP_THRESHOLD:
                # Linear slowdown between thresholds
                ratio = (agent.local_density - DENSITY_SLOWDOWN_THRESHOLD) / \
                        (DENSITY_STOP_THRESHOLD - DENSITY_SLOWDOWN_THRESHOLD)
                agent.speed_modifier = max(0.3, 1.0 - ratio * 0.7)
            else:
                # Very crowded - shuffle speed
                agent.speed_modifier = 0.2
    
    def _update_agent_states(self, dt: float):
        """Update behavioral states for all agents based on context."""
        scenario_type = self.scenario_config.get("type")
        
        for agent in self.agents:
            agent.time_in_state += dt
            
            # Skip seated agents
            if agent.state == AgentState.SEATED:
                continue
            
            # Stadium-specific state transitions
            if scenario_type == "stadium":
                self._update_stadium_agent_state(agent, dt)
                continue
            
            # General state transitions
            if not agent.is_indoor:
                # Outdoor - queuing behavior
                if agent.y > self.holding_line_y and not self.gate_open:
                    agent.state = AgentState.QUEUING
                else:
                    agent.state = AgentState.WALKING
            else:
                # Indoor state based on context
                if agent.is_panicking:
                    agent.state = AgentState.EVACUATING
                elif agent.state == AgentState.ENTERING:
                    # Just entered, transition to walking
                    if agent.y > 2.0:
                        agent.state = AgentState.WALKING
                else:
                    agent.state = AgentState.WALKING
    
    def _update_stadium_agent_state(self, agent: Agent, dt: float):
        """Update agent state for stadium scenario."""
        if not agent.is_indoor:
            # Outdoor queuing
            agent.state = AgentState.QUEUING if not self.gate_open else AgentState.WALKING
            return
        
        # Indoor stadium behavior
        if agent.state == AgentState.ENTERING:
            # Moving toward assigned stand entrance
            if agent.y > 3.0:
                agent.state = AgentState.FINDING_SEAT
                self._assign_seat_to_agent(agent)
        
        elif agent.state == AgentState.FINDING_SEAT:
            # Check if reached seat
            if agent.seat_position:
                dist = np.sqrt((agent.x - agent.seat_position[0])**2 + 
                              (agent.y - agent.seat_position[1])**2)
                if dist < 0.5:
                    agent.state = AgentState.SEATED
                    agent.vx = 0
                    agent.vy = 0
        
        elif agent.state == AgentState.WALKING:
            # Just entered building, assign to a stand
            self._assign_stand_to_agent(agent)
            agent.state = AgentState.ENTERING
    
    def _assign_stand_to_agent(self, agent: Agent):
        """Assign agent to an available stadium stand."""
        # Find stand with most available seats
        available_stands = []
        for stand_id, stand in self.stadium_stands.items():
            if stand["gate_open"] and stand["current"] < stand["capacity"]:
                available_stands.append((stand_id, stand["capacity"] - stand["current"]))
        
        if not available_stands:
            # All full - assign to largest stand anyway
            agent.assigned_stand = "center"
        else:
            # Weighted random by availability
            total_avail = sum(a[1] for a in available_stands)
            r = random.uniform(0, total_avail)
            cumsum = 0
            for stand_id, avail in available_stands:
                cumsum += avail
                if r <= cumsum:
                    agent.assigned_stand = stand_id
                    break
        
        # Set goal to stand entrance
        stand = self.stadium_stands[agent.assigned_stand]
        agent.goal_x, agent.goal_y = stand["entrance"]
    
    def _assign_seat_to_agent(self, agent: Agent):
        """Assign an empty seat to the agent."""
        if not agent.assigned_stand or agent.assigned_stand not in self.seats:
            return
        
        stand_seats = self.seats[agent.assigned_stand]
        
        # Find first empty seat (front-to-back filling)
        for i, (x, y, occupied) in enumerate(stand_seats):
            if not occupied:
                agent.seat_position = (x, y)
                agent.goal_x = x
                agent.goal_y = y
                # Mark seat as occupied
                self.seats[agent.assigned_stand][i] = (x, y, True)
                self.stadium_stands[agent.assigned_stand]["current"] += 1
                
                # Check if stand is now full
                stand = self.stadium_stands[agent.assigned_stand]
                if stand["current"] >= stand["capacity"]:
                    stand["gate_open"] = False
                return
        
        # No seats available - wander in stand area
        bounds = self.stadium_stands[agent.assigned_stand]["bounds"]
        agent.goal_x = random.uniform(bounds["x_min"] + 1, bounds["x_max"] - 1)
        agent.goal_y = random.uniform(bounds["y_min"] + 1, bounds["y_max"] - 1)
    
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
        Advance simulation by one time step with realistic crowd behavior.
        
        Args:
            dt: Time step in seconds (~15 FPS = 0.067s)
            gate_open: Whether the gate is open for entry
        """
        self.tick += 1
        self.gate_open = gate_open
        scenario_type = self.scenario_config.get("type")
        
        # Bidirectional flow control (Scenario 7)
        if scenario_type == "bidirectional":
            self.bidirectional_timer += dt
            if self.bidirectional_timer >= self.bidirectional_interval:
                self.bidirectional_timer = 0.0
                # Switch modes
                if self.bidirectional_mode == "entry":
                    self.bidirectional_mode = "exit"
                    self._switch_to_exit_mode()
                else:
                    self.bidirectional_mode = "entry"
                    self._switch_to_entry_mode()
        
        # Spawn new outdoor agents (scenario-dependent)
        if self.spawn_rate > 0:
            self.spawn_timer += dt
            if self.spawn_timer >= 1.0 / self.spawn_rate:
                self.spawn_timer = 0.0
                if len([a for a in self.agents if not a.is_indoor]) < 50:  # Cap outdoor
                    self.spawn_outdoor_agent()
        
        if not self.agents:
            return
        
        # Environment awareness - compute local densities for realistic behavior
        self._compute_local_densities()
        
        # Update behavioral states based on context
        self._update_agent_states(dt)
        
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
                    agent.state = AgentState.QUEUING
        
        # Handle transitions through door
        self._handle_door_transitions()
        
        # Scenario-specific handling
        scenario_type = self.scenario_config.get("type")
        
        if scenario_type == "stadium":
            # Stadium-specific logic
            self._handle_stadium_logic()
        elif self.scenario_config.get("has_exit"):
            if scenario_type == "basic":
                self._handle_exits()  # Top exit (Scenario 1)
            elif scenario_type == "bidirectional":
                self._handle_bidirectional_exits()  # Door exit (Scenario 7)
            elif scenario_type == "evacuation":
                self._handle_evacuation_exits()  # Emergency exits (Scenario 3)
        
        # Update goals for wandering agents (Scenario 2)
        if self.scenario == 2:
            self._update_wandering_goals()
    
    def _handle_stadium_logic(self):
        """Handle stadium-specific behavior: stand gates, seating, etc."""
        # Update stand occupancy counts
        for stand_id in self.stadium_stands:
            self.stadium_stands[stand_id]["current"] = 0
        
        for agent in self.agents:
            if agent.state == AgentState.SEATED and agent.assigned_stand:
                self.stadium_stands[agent.assigned_stand]["current"] += 1
        
        # Check if all stands are full - close main gate
        all_full = all(stand["current"] >= stand["capacity"] 
                      for stand in self.stadium_stands.values())
        if all_full:
            self.gate_open = False
    
    def _simple_physics_step(self, dt: float):
        """Simple physics when PySocialForce not available - with environment awareness."""
        for agent in self.agents:
            # Seated agents don't move
            if agent.state == AgentState.SEATED:
                agent.vx = 0
                agent.vy = 0
                continue
            
            # Move towards goal
            dx = agent.goal_x - agent.x
            dy = agent.goal_y - agent.y
            dist = np.sqrt(dx**2 + dy**2)
            
            # Base velocity with speed modifier for density
            vel = SLOW_VELOCITY if agent.is_slow else NORMAL_VELOCITY
            vel *= agent.speed_modifier
            
            # Panicking agents move faster but erratically
            if agent.is_panicking:
                vel *= 1.5
                # Add slight randomness to direction
                dx += random.uniform(-0.3, 0.3)
                dy += random.uniform(-0.3, 0.3)
            
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
        scenario_type = self.scenario_config.get("type")
        
        for agent in self.agents:
            # Check if near door
            if door_left <= agent.x <= door_right:
                if not agent.is_indoor and agent.y >= -0.5 and self.gate_open:
                    # Transition to indoor
                    agent.is_indoor = True
                    agent.y = max(agent.y, 1.0)
                    agent.state = AgentState.ENTERING
                    agent.time_in_state = 0.0
                    
                    # Set new goal based on scenario
                    if scenario_type == "stadium":
                        # Stadium: assign to a stand and set initial walking goal
                        agent.state = AgentState.WALKING
                        # Will be assigned to stand in _update_stadium_agent_state
                    elif self.scenario == 1:  # Entry + Exit
                        agent.goal_x = EXIT_X
                        agent.goal_y = INDOOR_HEIGHT + 1
                        agent.state = AgentState.WALKING
                    elif scenario_type == "evacuation":
                        # Will panic and exit
                        agent.is_panicking = True
                        agent.state = AgentState.EVACUATING
                        self._assign_evacuation_exit(agent)
                    elif scenario_type == "bidirectional":
                        # Wander briefly, then exit
                        agent.goal_x = random.uniform(5, INDOOR_WIDTH - 5)
                        agent.goal_y = random.uniform(5, INDOOR_HEIGHT - 5)
                        agent.state = AgentState.WANDERING
                    else:
                        # Random wandering
                        agent.goal_x = random.uniform(3, INDOOR_WIDTH - 3)
                        agent.goal_y = random.uniform(3, INDOOR_HEIGHT - 3)
                        agent.state = AgentState.WANDERING
    
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
    
    def _handle_bidirectional_exits(self):
        """Handle agents exiting through door in bidirectional mode (Scenario 7)."""
        door_left = DOOR_X - DOOR_WIDTH / 2
        door_right = DOOR_X + DOOR_WIDTH / 2
        
        to_remove = []
        for agent in self.agents:
            if agent.is_indoor and agent.y <= 0.5:
                if door_left <= agent.x <= door_right:
                    to_remove.append(agent)
        
        for agent in to_remove:
            self.agents.remove(agent)
    
    def _handle_evacuation_exits(self):
        """Handle agents exiting during evacuation (Scenario 3)."""
        to_remove = []
        
        for agent in self.agents:
            # Main door exit
            door_left = DOOR_X - DOOR_WIDTH / 2
            door_right = DOOR_X + DOOR_WIDTH / 2
            if agent.y <= 0.5 and door_left <= agent.x <= door_right:
                to_remove.append(agent)
            
            # Left emergency exit
            elif agent.x <= 0.5 and abs(agent.y - INDOOR_HEIGHT / 2) <= 1.0:
                to_remove.append(agent)
            
            # Right emergency exit
            elif agent.x >= INDOOR_WIDTH - 0.5 and abs(agent.y - INDOOR_HEIGHT / 2) <= 1.0:
                to_remove.append(agent)
        
        for agent in to_remove:
            self.agents.remove(agent)
    
    def _assign_evacuation_exit(self, agent: Agent):
        """Assign nearest emergency exit to agent."""
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
    
    def _switch_to_exit_mode(self):
        """Switch bidirectional flow to exit mode."""
        # Set indoor agents to exit through door
        for agent in self.agents:
            if agent.is_indoor:
                agent.goal_x = DOOR_X
                agent.goal_y = -1
    
    def _switch_to_entry_mode(self):
        """Switch bidirectional flow to entry mode."""
        # Outdoor agents will continue entering
        # Indoor agents wander
        for agent in self.agents:
            if agent.is_indoor:
                agent.goal_x = random.uniform(5, INDOOR_WIDTH - 5)
                agent.goal_y = random.uniform(5, INDOOR_HEIGHT - 5)
                agent.state = AgentState.WANDERING
    
    def start_evacuation(self):
        """Start evacuation mode (Scenario 3)."""
        self.scenario = 3
        self.scenario_config = get_scenario(3)
        self.gate_open = False
        self.spawn_rate = 0.0  # No new spawns during evacuation
        
        # Set all indoor agents to panic and exit
        for agent in self.agents:
            if agent.is_indoor:
                agent.is_panicking = True
                agent.state = AgentState.EVACUATING
                self._assign_evacuation_exit(agent)
    
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
        """Get agent state for WebSocket broadcast with behavior info."""
        # State encoding for frontend
        state_map = {
            AgentState.QUEUING: 0,
            AgentState.WALKING: 1,
            AgentState.ENTERING: 2,
            AgentState.FINDING_SEAT: 3,
            AgentState.SEATED: 4,
            AgentState.EVACUATING: 5,
            AgentState.WANDERING: 6
        }
        
        return [
            [
                round(a.x, 2),
                round(a.y, 2),
                round(a.vx, 2),
                round(a.vy, 2),
                1 if a.is_slow else 0,
                1 if a.is_panicking else 0,
                state_map.get(a.state, 1),  # Behavioral state
                round(a.local_density, 2),   # Local density for debugging
                a.assigned_stand or ""       # Stadium stand assignment
            ]
            for a in self.agents
        ]
    
    def get_stadium_stats(self) -> Dict:
        """Get stadium-specific statistics for frontend display."""
        if self.scenario_config.get("type") != "stadium":
            return {}
        
        return {
            "stands": {
                stand_id: {
                    "name": stand["name"],
                    "current": stand["current"],
                    "capacity": stand["capacity"],
                    "gate_open": stand["gate_open"],
                    "utilization": round(stand["current"] / stand["capacity"] * 100, 1) if stand["capacity"] > 0 else 0
                }
                for stand_id, stand in self.stadium_stands.items()
            },
            "total_seated": sum(1 for a in self.agents if a.state == AgentState.SEATED),
            "total_capacity": sum(s["capacity"] for s in self.stadium_stands.values()),
            "all_full": all(s["current"] >= s["capacity"] for s in self.stadium_stands.values())
        }
