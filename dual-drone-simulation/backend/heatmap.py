"""
Heatmap generation and crush risk computation using SciPy gaussian filter.
"""
import numpy as np
from scipy.ndimage import gaussian_filter

# World dimensions (simulation units)
INDOOR_WIDTH = 20
INDOOR_HEIGHT = 20
OUTDOOR_WIDTH = 20
OUTDOOR_HEIGHT = 15
DOOR_Y = 20  # Y position where indoor meets outdoor

def compute_heatmap(agent_positions: list, zone: str = "indoor", grid_size: int = 50, sigma: float = 2.0) -> list:
    """
    Compute a gaussian-smoothed density heatmap from agent positions.
    
    Args:
        agent_positions: List of [x, y] positions
        zone: "indoor" or "outdoor" to determine world dimensions
        grid_size: Resolution of the heatmap grid
        sigma: Gaussian smoothing parameter
    
    Returns:
        2D list representing the heatmap
    """
    if zone == "indoor":
        world_width, world_height = INDOOR_WIDTH, INDOOR_HEIGHT
    else:
        world_width, world_height = OUTDOOR_WIDTH, OUTDOOR_HEIGHT
    
    heatmap = np.zeros((grid_size, grid_size))
    
    for pos in agent_positions:
        x, y = pos[0], pos[1]
        xi = int(np.clip(x / world_width * grid_size, 0, grid_size - 1))
        yi = int(np.clip(y / world_height * grid_size, 0, grid_size - 1))
        heatmap[yi, xi] += 1
    
    smoothed = gaussian_filter(heatmap, sigma=sigma)
    return smoothed.tolist()


def compute_crush_risk_index(agent_positions: list, zone: str = "indoor", grid_size: int = 10) -> float:
    """
    Compute crush risk index as average density of top-5 highest-density cells.
    
    The floor plan is divided into a grid, and local density is computed per cell.
    High local density indicates potential crush risk even at low overall occupancy.
    
    Args:
        agent_positions: List of [x, y] positions
        zone: "indoor" or "outdoor"
        grid_size: Number of cells per dimension (10x10 default)
    
    Returns:
        Crush risk index (agents per unit area in highest-density regions)
    """
    if zone == "indoor":
        world_width, world_height = INDOOR_WIDTH, INDOOR_HEIGHT
    else:
        world_width, world_height = OUTDOOR_WIDTH, OUTDOOR_HEIGHT
    
    if len(agent_positions) == 0:
        return 0.0
    
    # Count agents per cell
    cell_counts = np.zeros((grid_size, grid_size))
    cell_width = world_width / grid_size
    cell_height = world_height / grid_size
    cell_area = cell_width * cell_height
    
    for pos in agent_positions:
        x, y = pos[0], pos[1]
        xi = int(np.clip(x / world_width * grid_size, 0, grid_size - 1))
        yi = int(np.clip(y / world_height * grid_size, 0, grid_size - 1))
        cell_counts[yi, xi] += 1
    
    # Convert to density (agents per unit area)
    densities = cell_counts / cell_area
    
    # Get top-5 highest density cells
    flat_densities = densities.flatten()
    top_5 = np.sort(flat_densities)[-5:]
    
    return float(np.mean(top_5))


def get_exit_compression(agent_positions: list, exit_points: list, radius: float = 3.0) -> float:
    """
    Compute compression score at exit points for evacuation scenarios.
    
    Args:
        agent_positions: List of [x, y] positions
        exit_points: List of [x, y] exit center positions
        radius: Radius around exit to measure density
    
    Returns:
        Maximum density at any exit point
    """
    if len(agent_positions) == 0 or len(exit_points) == 0:
        return 0.0
    
    positions = np.array(agent_positions)
    max_density = 0.0
    area = np.pi * radius ** 2
    
    for exit_pos in exit_points:
        ex, ey = exit_pos
        distances = np.sqrt((positions[:, 0] - ex)**2 + (positions[:, 1] - ey)**2)
        count = np.sum(distances < radius)
        density = count / area
        max_density = max(max_density, density)
    
    return float(max_density)
