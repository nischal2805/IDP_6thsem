"""
FastAPI WebSocket server for dual-drone crowd simulation.
Broadcasts simulation state at ~15 FPS.
"""
import asyncio
import json
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

from crowd_sim import CrowdSimulation
from coordinator import Coordinator
from panic import PanicManager
from heatmap import compute_heatmap, compute_crush_risk_index, get_exit_compression
from zones import MultiZoneManager
from scenarios import get_scenario, get_all_scenarios

app = FastAPI(title="Dual Drone Crowd Simulation")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
simulation = CrowdSimulation(scenario=1)
coordinator = Coordinator(capacity=100)
panic_manager = PanicManager()
zone_manager = MultiZoneManager(scenario_type="basic")
connected_clients: Set[WebSocket] = set()
sim_running = False
sim_task = None
current_scenario_id = 1

# History buffer for replay
history_buffer = []
MAX_HISTORY = 300


async def broadcast_state():
    """Broadcast current simulation state to all connected clients."""
    indoor_agents = simulation.get_indoor_agents()
    outdoor_agents = simulation.get_outdoor_agents()
    
    indoor_positions = [[a.x, a.y] for a in indoor_agents]
    outdoor_positions = [[a.x, a.y] for a in outdoor_agents]
    
    # Compute metrics
    crush_risk = compute_crush_risk_index(indoor_positions, "indoor")
    exit_compression = 0.0
    
    if coordinator.evacuation_active:
        exit_points = [[10, 0], [0, 10], [20, 10]]  # Main door + emergency exits
        exit_compression = get_exit_compression(indoor_positions, exit_points)
    
    # Update zone counts if zones active
    zone_stats = []
    lane_stats = []
    scenario_config = get_scenario(current_scenario_id)
    
    if scenario_config.get("has_zones"):
        zone_manager.update_zone_counts(simulation.agents)
        zone_stats = zone_manager.get_zone_stats()
        lane_stats = zone_manager.get_lane_stats()
    
    # Update coordinator
    coord_state = coordinator.update(
        indoor_count=len(indoor_agents),
        outdoor_count=len(outdoor_agents),
        crush_risk=crush_risk,
        exit_compression=exit_compression
    )
    
    # Compute heatmaps (lower resolution for performance)
    indoor_heatmap = compute_heatmap(indoor_positions, "indoor", grid_size=25, sigma=1.5)
    outdoor_heatmap = compute_heatmap(outdoor_positions, "outdoor", grid_size=25, sigma=1.5)
    
    # Build payload
    payload = {
        "tick": simulation.tick,
        "agents": simulation.get_state_for_broadcast(),
        "indoor_count": len(indoor_agents),
        "outdoor_count": len(outdoor_agents),
        "capacity": coordinator.capacity,
        "status": coord_state["status"],
        "gate": coord_state["gate"],
        "scenario": current_scenario_id,
        "scenario_config": scenario_config,
        "scenario_type": scenario_config.get("type", "basic"),
        "crush_risk_index": round(crush_risk, 2),
        "crush_warning": coord_state.get("crush_warning", False),
        "crush_critical": coord_state.get("crush_critical", False),
        "evacuation_pct": coord_state.get("evacuation_pct"),
        "evacuation_complete": coord_state.get("evacuation_complete", False),
        "indoor_heatmap": indoor_heatmap,
        "outdoor_heatmap": outdoor_heatmap,
        "history": coordinator.get_history()[-50:],  # Last 50 points for chart
        "drone_a": coordinator.get_drone_a_status(len(indoor_agents), crush_risk),
        "drone_b": coordinator.get_drone_b_status(len(outdoor_agents)),
        "panic_active": len(panic_manager.get_panic_state()["panicking_agents"]) > 0,
        "zones": zone_stats,
        "lanes": lane_stats
    }
    
    # Record history
    history_buffer.append({
        "tick": simulation.tick,
        "indoor_count": len(indoor_agents),
        "outdoor_count": len(outdoor_agents),
        "status": coord_state["status"],
        "crush_risk_index": round(crush_risk, 2)
    })
    if len(history_buffer) > MAX_HISTORY:
        history_buffer.pop(0)
    
    # Broadcast to all clients
    message = json.dumps(payload)
    disconnected = set()
    
    for client in connected_clients:
        try:
            await client.send_text(message)
        except:
            disconnected.add(client)
    
    connected_clients.difference_update(disconnected)


async def simulation_loop():
    """Main simulation loop running at ~15 FPS."""
    global sim_running
    
    dt = 0.067  # ~15 FPS
    
    while sim_running:
        # Check gate state
        gate_open = coordinator.gate.value != "CLOSED"
        if coordinator.gate.value == "THROTTLE":
            gate_open = coordinator._can_admit_agent()
        
        # Step simulation
        simulation.step(dt=dt, gate_open=gate_open)
        
        # Propagate panic
        if panic_manager.panic_flags:
            import numpy as np
            states = np.array([[a.x, a.y, a.vx, a.vy, a.goal_x, a.goal_y] for a in simulation.agents])
            if len(states) > 0:
                panicking = panic_manager.propagate_panic(states, dt)
                for i, agent in enumerate(simulation.agents):
                    agent.is_panicking = i in panicking
        
        # Broadcast state
        await broadcast_state()
        
        # Wait for next frame
        await asyncio.sleep(dt)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time simulation updates."""
    await websocket.accept()
    connected_clients.add(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            await handle_command(message)
    except WebSocketDisconnect:
        connected_clients.discard(websocket)


async def handle_command(message: dict):
    """Handle commands from frontend."""
    global sim_running, sim_task, current_scenario_id, zone_manager
    
    cmd = message.get("command")
    
    if cmd == "start":
        if not sim_running:
            scenario = message.get("scenario", 1)
            current_scenario_id = scenario
            capacity = message.get("capacity", 100)
            initial_indoor = message.get("initial_indoor", 20)
            initial_outdoor = message.get("initial_outdoor", 10)
            
            simulation.reset(scenario=scenario)
            coordinator.reset(scenario=scenario, capacity=capacity)
            panic_manager.reset()
            history_buffer.clear()
            
            # Initialize zones for zone-based scenarios
            scenario_config = get_scenario(scenario)
            if scenario_config.get("has_zones"):
                zone_manager = MultiZoneManager(scenario_type=scenario_config.get("zone_type", "basic"))
            else:
                zone_manager = MultiZoneManager(scenario_type="basic")
            
            simulation.spawn_initial_crowd(initial_indoor, initial_outdoor)
            
            sim_running = True
            sim_task = asyncio.create_task(simulation_loop())
    
    elif cmd == "stop":
        sim_running = False
        if sim_task:
            sim_task.cancel()
            try:
                await sim_task
            except asyncio.CancelledError:
                pass
    
    elif cmd == "reset":
        # Reset simulation to initial state
        sim_running = False
        if sim_task:
            sim_task.cancel()
            try:
                await sim_task
            except asyncio.CancelledError:
                pass
        
        simulation.reset(scenario=current_scenario_id)
        coordinator.reset(scenario=current_scenario_id, capacity=coordinator.capacity)
        panic_manager.reset()
        history_buffer.clear()
        
        # Reset zones
        scenario_config = get_scenario(current_scenario_id)
        if scenario_config.get("has_zones"):
            zone_manager = MultiZoneManager(scenario_type=scenario_config.get("zone_type", "basic"))
        else:
            zone_manager = MultiZoneManager(scenario_type="basic")
    
    elif cmd == "pause":
        sim_running = False
    
    elif cmd == "resume":
        if not sim_running and simulation.tick > 0:
            sim_running = True
            sim_task = asyncio.create_task(simulation_loop())
    
    elif cmd == "inject_panic":
        x = message.get("x", 10)
        y = message.get("y", 10)
        import numpy as np
        states = np.array([[a.x, a.y, a.vx, a.vy, a.goal_x, a.goal_y] for a in simulation.agents])
        if len(states) > 0:
            panic_manager.inject_panic(x, y, states, radius=5.0)
    
    elif cmd == "start_evacuation":
        simulation.start_evacuation()
        coordinator.start_evacuation(len(simulation.get_indoor_agents()))
    
    elif cmd == "set_capacity":
        coordinator.capacity = message.get("capacity", 100)
    
    elif cmd == "set_spawn_rate":
        simulation.spawn_rate = message.get("rate", 2.0)
    
    elif cmd == "get_scenarios":
        # Return list of all scenarios
        for client in connected_clients:
            try:
                await client.send_text(json.dumps({
                    "type": "scenarios_list",
                    "data": get_all_scenarios()
                }))
            except:
                pass
    
    elif cmd == "get_history":
        # Return full history for export
        for client in connected_clients:
            try:
                await client.send_text(json.dumps({
                    "type": "history_export",
                    "data": history_buffer
                }))
            except:
                pass


@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "name": "Dual Drone Crowd Simulation",
        "status": "running" if sim_running else "stopped",
        "websocket": "/ws"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    print("Starting Dual Drone Crowd Simulation Server...")
    print("WebSocket endpoint: ws://localhost:8000/ws")
    print("Open the frontend to connect and control the simulation.")
    uvicorn.run(app, host="0.0.0.0", port=8000)
