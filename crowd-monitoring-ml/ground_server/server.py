"""
Ground Server - FastAPI WebSocket Server for Dashboard.
Receives Jetson inference data, runs LSTM forecasting, serves React dashboard.
"""
import asyncio
import json
import time
import struct
from typing import Dict, Set, Optional, List
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from lstm_forecaster import CrowdDensityForecaster, generate_synthetic_data
from telegram_bot import TelegramAlertBot, MockTelegramBot

# Configuration
JETSON_PORT = 9000
DASHBOARD_PORT = 8080
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = [int(x) for x in os.environ.get("TELEGRAM_CHAT_IDS", "").split(",") if x]


@dataclass
class SystemState:
    """Current system state."""
    connected_jetson: bool = False
    last_jetson_data: Optional[Dict] = None
    last_update: float = 0
    total_frames: int = 0
    active_alerts: List[Dict] = None
    forecast: Optional[Dict] = None
    latest_frame: Optional[bytes] = None  # Latest JPEG frame from Jetson
    
    def __post_init__(self):
        if self.active_alerts is None:
            self.active_alerts = []


# Global state
state = SystemState()
forecaster = CrowdDensityForecaster(window_size=30, capacity=100)
telegram_bot = None
dashboard_clients: Set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global telegram_bot
    
    # Initialize Telegram bot
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_IDS:
        telegram_bot = TelegramAlertBot(TELEGRAM_TOKEN, TELEGRAM_CHAT_IDS)
        await telegram_bot.start()
    else:
        telegram_bot = MockTelegramBot()
        print("Using mock Telegram bot (no credentials)")
    
    # Start Jetson listener
    asyncio.create_task(jetson_listener())
    
    # Start periodic status broadcast
    asyncio.create_task(periodic_status_update())
    
    yield
    
    # Cleanup
    if hasattr(telegram_bot, 'stop'):
        await telegram_bot.stop()


app = FastAPI(
    title="Crowd Monitoring Ground Server",
    description="Receives drone inference data and serves dashboard",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:8080",  # Production dashboard
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Jetson Data Receiver ====================

async def jetson_listener():
    """
    TCP server receiving data from Jetson.
    Protocol: 4-byte length prefix + JSON payload
    """
    server = await asyncio.start_server(
        handle_jetson_connection,
        '0.0.0.0',
        JETSON_PORT
    )
    
    addr = server.sockets[0].getsockname()
    print(f"Jetson listener started on {addr}")
    
    async with server:
        await server.serve_forever()


async def handle_jetson_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle connection from Jetson device."""
    addr = writer.get_extra_info('peername')
    print(f"✅ Jetson connected from {addr}")
    state.connected_jetson = True
    
    frame_count = 0
    data_only_count = 0
    
    try:
        while True:
            # Read length prefix for JSON
            length_bytes = await reader.readexactly(4)
            length = struct.unpack('>I', length_bytes)[0]
            
            # Read JSON payload
            data_bytes = await reader.readexactly(length)
            packet = json.loads(data_bytes.decode('utf-8'))
            
            packet_type = packet.get('type', 'unknown')
            
            # Handle packet with video frame
            if packet_type == 'inference' and 'frame_size' in packet:
                frame_size = packet['frame_size']
                # Read JPEG frame
                frame_bytes = await reader.readexactly(frame_size)
                # Store latest frame
                state.latest_frame = frame_bytes
                
                frame_count += 1
                if frame_count == 1:
                    print(f"📸 First video frame received: {frame_size/1024:.1f}KB JPEG")
                elif frame_count % 100 == 0:
                    print(f"📸 Received {frame_count} video frames (latest: {frame_size/1024:.1f}KB)")
                
                # Process inference data
                await process_jetson_data(packet['data'])
                
            # Handle data-only packet (no video frame)
            elif packet_type == 'inference_data_only':
                data_only_count += 1
                if data_only_count == 1:
                    print(f"⚠️ Jetson sending data WITHOUT video frames - check camera/encoding on Jetson")
                elif data_only_count % 100 == 0:
                    print(f"⚠️ Received {data_only_count} data-only packets (no video)")
                await process_jetson_data(packet['data'])
                
            # Handle old format (backwards compatibility)
            else:
                if frame_count == 0 and data_only_count == 0:
                    print(f"⚠️ Jetson using old packet format (no 'type' field) - video won't work")
                await process_jetson_data(packet)
            
    except asyncio.IncompleteReadError:
        print("Jetson disconnected")
    except Exception as e:
        print(f"Jetson connection error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        state.connected_jetson = False
        writer.close()
        await writer.wait_closed()


async def process_jetson_data(data: Dict):
    """Process incoming Jetson inference data."""
    global state
    
    state.last_jetson_data = data
    state.last_update = time.time()
    state.total_frames += 1
    
    # Log basic stats every 30 frames
    if state.total_frames % 30 == 0:
        person_count = data.get("person_count", 0)
        density_count = data.get("density", {}).get("count", 0)
        alert_count = len(data.get("alerts", []))
        print(f"📊 Jetson data received | Frame: {state.total_frames} | Persons: {person_count} | Density: {density_count:.0f} | Alerts: {alert_count}")
    
    # Update forecaster with density count
    density_count = data.get("density", {}).get("count", 0)
    forecaster.update(density_count)
    
    # Generate forecast
    forecast_result = forecaster.predict()
    if forecast_result:
        state.forecast = forecaster.to_dict(forecast_result)
    
    # Process alerts
    alerts = data.get("alerts", [])
    for alert in alerts:
        await handle_alert(alert)
        state.active_alerts.append(alert)
    
    # Keep only recent alerts
    state.active_alerts = state.active_alerts[-50:]
    
    # Broadcast to dashboard clients
    await broadcast_to_dashboard({
        "type": "inference_update",
        "data": data,
        "forecast": state.forecast,
        "server_time": time.time()
    })


async def handle_alert(alert: Dict):
    """Send alert via Telegram."""
    alert_type = alert.get("type")
    location = alert.get("location", {})
    
    print(f"📢 Processing alert: {alert_type.upper()} | ID: {alert.get('alert_id', 'UNKNOWN')} | Confidence: {alert.get('confidence', 0):.2f}")
    
    if alert_type == "fall":
        await telegram_bot.send_fall_alert(
            alert_id=alert.get("alert_id", "UNKNOWN"),
            person_id=alert.get("person_id", 0),
            confidence=alert.get("confidence", 0),
            gps_lat=location.get("lat"),
            gps_lng=location.get("lng"),
            duration=alert.get("data", {}).get("duration_seconds", 0)
        )
        print(f"   ✅ Fall alert sent to Telegram")
    
    elif alert_type == "panic":
        await telegram_bot.send_panic_alert(
            alert_id=alert.get("alert_id", "UNKNOWN"),
            confidence=alert.get("confidence", 0),
            affected_count=alert.get("data", {}).get("estimated_people", 0),
            gps_lat=location.get("lat"),
            gps_lng=location.get("lng"),
            severity=alert.get("data", {}).get("severity", "HIGH")
        )
        print(f"   ✅ Panic alert sent to Telegram")
    
    elif alert_type == "crush_risk":
        await telegram_bot.send_crush_risk_alert(
            alert_id=alert.get("alert_id", "UNKNOWN"),
            density=alert.get("data", {}).get("density", 0),
            gps_lat=location.get("lat"),
            gps_lng=location.get("lng")
        )
        print(f"   ✅ Crush risk alert sent to Telegram")


# ==================== Dashboard WebSocket ====================

@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """WebSocket endpoint for React dashboard."""
    await websocket.accept()
    dashboard_clients.add(websocket)
    
    # Send current state on connect
    await websocket.send_json({
        "type": "initial_state",
        "connected_jetson": state.connected_jetson,
        "last_data": state.last_jetson_data,
        "forecast": state.forecast,
        "active_alerts": state.active_alerts[-10:]
    })
    
    try:
        while True:
            # Receive commands from dashboard
            data = await websocket.receive_json()
            await handle_dashboard_command(data, websocket)
    except WebSocketDisconnect:
        dashboard_clients.discard(websocket)


async def handle_dashboard_command(data: Dict, websocket: WebSocket):
    """Handle commands from dashboard."""
    command = data.get("command")
    
    if command == "get_history":
        history = forecaster.get_history()
        await websocket.send_json({
            "type": "history",
            "data": history
        })
    
    elif command == "get_alerts":
        await websocket.send_json({
            "type": "alerts",
            "data": state.active_alerts
        })
    
    elif command == "acknowledge_alert":
        alert_id = data.get("alert_id")
        # Mark as acknowledged
        for alert in state.active_alerts:
            if alert.get("alert_id") == alert_id:
                alert["acknowledged"] = True
        await broadcast_to_dashboard({
            "type": "alert_acknowledged",
            "alert_id": alert_id
        })


async def broadcast_to_dashboard(message: Dict):
    """Broadcast message to all connected dashboard clients."""
    disconnected = set()
    
    for client in dashboard_clients:
        try:
            await client.send_json(message)
        except WebSocketDisconnect:
            disconnected.add(client)
        except Exception as e:
            print(f"⚠️ Error broadcasting to dashboard client: {e}")
            disconnected.add(client)
    
    dashboard_clients.difference_update(disconnected)
    if disconnected:
        print(f"📊 Removed {len(disconnected)} disconnected dashboard client(s). Active: {len(dashboard_clients)}")


async def periodic_status_update():
    """Send periodic status updates to Telegram."""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        
        if state.forecast and telegram_bot:
            await telegram_bot.send_status_update(
                crowd_count=int(state.forecast.get("current", 0)),
                density_forecast=state.forecast.get("predictions", {}),
                active_alerts=len([a for a in state.active_alerts if not a.get("acknowledged")])
            )


# ==================== REST API Endpoints ====================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Crowd Monitoring Ground Server",
        "version": "1.0.0",
        "jetson_connected": state.connected_jetson,
        "dashboard_clients": len(dashboard_clients),
        "total_frames": state.total_frames
    }


@app.get("/api/status")
async def get_status():
    """Get current system status."""
    return {
        "jetson_connected": state.connected_jetson,
        "last_update": state.last_update,
        "total_frames": state.total_frames,
        "forecast": state.forecast,
        "active_alerts": len(state.active_alerts),
        "dashboard_clients": len(dashboard_clients)
    }


@app.get("/api/forecast")
async def get_forecast():
    """Get current density forecast."""
    if state.forecast:
        return state.forecast
    raise HTTPException(status_code=404, detail="No forecast available")


@app.get("/api/alerts")
async def get_alerts(limit: int = 50):
    """Get recent alerts."""
    return {"alerts": state.active_alerts[-limit:], "total": len(state.active_alerts)}


@app.post("/api/alerts/clear")
async def clear_test_alerts():
    """Clear all test alerts (development only)."""
    global state
    old_count = len(state.active_alerts)
    
    # Clear only test alerts
    state.active_alerts = [a for a in state.active_alerts if not a.get("alert_id", "").startswith("TEST")]
    cleared = old_count - len(state.active_alerts)
    
    # Broadcast update
    await broadcast_to_dashboard({
        "type": "alerts_cleared",
        "cleared_count": cleared
    })
    
    return {"status": "ok", "cleared": cleared, "remaining": len(state.active_alerts)}


@app.get("/api/history")
async def get_history():
    """Get density history."""
    return {
        "history": forecaster.get_history(),
        "length": len(forecaster.get_history())
    }


@app.get("/api/video_feed")
async def video_feed():
    """Stream latest JPEG frame from Jetson."""
    from fastapi.responses import Response
    
    if state.latest_frame:
        return Response(
            content=state.latest_frame, 
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    else:
        # Debug info
        debug_msg = f"No video frame available. Jetson connected: {state.connected_jetson}, Frames received: {state.total_frames}"
        print(f"⚠️ Video feed requested but no frame: {debug_msg}")
        raise HTTPException(status_code=404, detail=debug_msg)


@app.post("/api/test/alert")
async def create_test_alert(alert_type: str = "fall"):
    """Create a test alert for development."""
    alert = {
        "alert_id": f"TEST-{int(time.time())}",
        "type": alert_type,
        "timestamp": time.time(),
        "confidence": 0.95,
        "location": {"lat": 12.9236, "lng": 77.4987},
        "data": {"test": True}
    }
    
    await handle_alert(alert)
    state.active_alerts.append(alert)
    
    return {"status": "ok", "alert": alert}


@app.post("/api/forecaster/train")
async def train_forecaster(epochs: int = 50):
    """Train forecaster on synthetic data (for demo)."""
    from lstm_forecaster import ForecasterTrainer, LSTMForecaster, generate_synthetic_data
    import torch
    
    # Generate data
    train_data = generate_synthetic_data(duration_seconds=3600)
    val_data = generate_synthetic_data(duration_seconds=600)
    
    # Create and train model
    model = LSTMForecaster()
    trainer = ForecasterTrainer(model, device="cpu")
    
    history = trainer.train(
        train_data=train_data,
        val_data=val_data,
        epochs=epochs,
        save_path="models/forecaster_model.pt"
    )
    
    return {
        "status": "training_complete",
        "final_train_loss": history["train_loss"][-1],
        "final_val_loss": history["val_loss"][-1]
    }


# ==================== Main ====================

def main():
    """Run the ground server."""
    print("=" * 50)
    print("Crowd Monitoring Ground Server")
    print("=" * 50)
    print(f"Jetson listener port: {JETSON_PORT}")
    print(f"Dashboard HTTP port: {DASHBOARD_PORT}")
    print(f"Telegram configured: {bool(TELEGRAM_TOKEN)}")
    print("=" * 50)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=DASHBOARD_PORT,
        log_level="info"
    )


if __name__ == "__main__":
    main()
