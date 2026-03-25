"""
GPS Alert Module for Distress Events.
Interfaces with Pixhawk via MAVLink to get GPS coordinates on fall detection.
"""
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from threading import Thread, Lock
import json

try:
    from pymavlink import mavutil
    MAVLINK_AVAILABLE = True
except ImportError:
    MAVLINK_AVAILABLE = False
    print("Warning: pymavlink not installed. GPS features disabled.")


@dataclass
class GPSFix:
    """Represents a GPS position fix."""
    latitude: float
    longitude: float
    altitude: float  # meters MSL
    accuracy: float  # horizontal accuracy in meters
    timestamp: float
    num_satellites: int
    fix_type: int  # 0=no fix, 2=2D, 3=3D
    
    def to_dict(self) -> Dict:
        return {
            "lat": self.latitude,
            "lng": self.longitude,
            "alt": self.altitude,
            "accuracy": self.accuracy,
            "timestamp": self.timestamp,
            "satellites": self.num_satellites,
            "fix_type": self.fix_type
        }
    
    def to_google_maps_url(self) -> str:
        return f"https://maps.google.com/?q={self.latitude},{self.longitude}"


@dataclass
class DistressAlert:
    """Represents a distress alert with location."""
    alert_id: str
    alert_type: str  # "fall", "panic", "crush_risk"
    timestamp: float
    gps: Optional[GPSFix]
    confidence: float
    person_id: Optional[int]
    additional_data: Dict
    
    def to_json(self) -> str:
        return json.dumps({
            "alert_id": self.alert_id,
            "type": self.alert_type,
            "timestamp": self.timestamp,
            "location": self.gps.to_dict() if self.gps else None,
            "confidence": self.confidence,
            "person_id": self.person_id,
            "data": self.additional_data
        })


class GPSManager:
    """
    Manages GPS coordinate retrieval from Pixhawk via MAVLink.
    Caches GPS fixes for low-latency alert generation.
    """
    
    def __init__(
        self,
        connection_string: str = "/dev/ttyACM0",  # USB
        baud_rate: int = 115200,
        cache_interval: float = 0.5  # seconds between cache updates
    ):
        """
        Initialize GPS manager.
        
        Args:
            connection_string: MAVLink connection string
                - Serial: /dev/ttyACM0 or /dev/ttyUSB0
                - UDP: udp:127.0.0.1:14550
                - TCP: tcp:127.0.0.1:5760
            baud_rate: Serial baud rate
            cache_interval: How often to cache GPS position
        """
        self.connection_string = connection_string
        self.baud_rate = baud_rate
        self.cache_interval = cache_interval
        
        self.mavlink_connection = None
        self.cached_fix: Optional[GPSFix] = None
        self.lock = Lock()
        
        self.running = False
        self.cache_thread: Optional[Thread] = None
        
        # Connection status
        self.is_connected = False
        self.last_heartbeat = 0
    
    def connect(self) -> bool:
        """
        Establish MAVLink connection to Pixhawk.
        
        Returns:
            True if connection successful
        """
        if not MAVLINK_AVAILABLE:
            print("pymavlink not available, using mock GPS")
            return self._connect_mock()
        
        try:
            self.mavlink_connection = mavutil.mavlink_connection(
                self.connection_string,
                baud=self.baud_rate
            )
            
            # Wait for heartbeat
            print("Waiting for heartbeat...")
            self.mavlink_connection.wait_heartbeat(timeout=10)
            self.is_connected = True
            self.last_heartbeat = time.time()
            
            print(f"Connected to {self.connection_string}")
            print(f"System ID: {self.mavlink_connection.target_system}")
            
            # Start cache thread
            self._start_cache_thread()
            
            return True
            
        except Exception as e:
            print(f"MAVLink connection failed: {e}")
            return self._connect_mock()
    
    def _connect_mock(self) -> bool:
        """Use mock GPS for testing."""
        self.is_connected = True
        self._start_cache_thread()
        return True
    
    def _start_cache_thread(self):
        """Start background thread for GPS caching."""
        self.running = True
        self.cache_thread = Thread(target=self._cache_loop, daemon=True)
        self.cache_thread.start()
    
    def _cache_loop(self):
        """Background loop to cache GPS position."""
        while self.running:
            try:
                fix = self._get_gps_raw()
                if fix:
                    with self.lock:
                        self.cached_fix = fix
            except Exception as e:
                print(f"GPS cache error: {e}")
            
            time.sleep(self.cache_interval)
    
    def _get_gps_raw(self) -> Optional[GPSFix]:
        """Get raw GPS data from MAVLink or mock."""
        if not MAVLINK_AVAILABLE or self.mavlink_connection is None:
            return self._get_mock_gps()
        
        try:
            # Request GPS_RAW_INT message
            msg = self.mavlink_connection.recv_match(
                type='GPS_RAW_INT',
                blocking=True,
                timeout=1.0
            )
            
            if msg:
                return GPSFix(
                    latitude=msg.lat / 1e7,
                    longitude=msg.lon / 1e7,
                    altitude=msg.alt / 1000.0,  # mm to m
                    accuracy=msg.eph / 100.0 if msg.eph else 999,  # cm to m
                    timestamp=time.time(),
                    num_satellites=msg.satellites_visible,
                    fix_type=msg.fix_type
                )
        except Exception as e:
            print(f"Error reading GPS: {e}")
        
        return None
    
    def _get_mock_gps(self) -> GPSFix:
        """Generate mock GPS fix for testing."""
        # RVCE coordinates with small random offset
        import random
        return GPSFix(
            latitude=12.9236 + random.uniform(-0.001, 0.001),
            longitude=77.4987 + random.uniform(-0.001, 0.001),
            altitude=920.0 + random.uniform(-5, 5),
            accuracy=2.5,
            timestamp=time.time(),
            num_satellites=12,
            fix_type=3
        )
    
    def get_current_position(self) -> Optional[GPSFix]:
        """
        Get current GPS position (from cache for low latency).
        
        Returns:
            Cached GPSFix or None if not available
        """
        with self.lock:
            return self.cached_fix
    
    def disconnect(self):
        """Close MAVLink connection."""
        self.running = False
        if self.cache_thread:
            self.cache_thread.join(timeout=2.0)
        
        if self.mavlink_connection:
            self.mavlink_connection.close()
        
        self.is_connected = False
    
    def get_status(self) -> Dict:
        """Get GPS manager status."""
        return {
            "connected": self.is_connected,
            "has_fix": self.cached_fix is not None,
            "last_fix": self.cached_fix.to_dict() if self.cached_fix else None,
            "fix_age_ms": (time.time() - self.cached_fix.timestamp) * 1000 if self.cached_fix else None
        }


class AlertManager:
    """
    Manages generation and dispatch of distress alerts.
    Packages alerts with GPS coordinates for transmission.
    """
    
    def __init__(self, gps_manager: Optional[GPSManager] = None):
        self.gps_manager = gps_manager
        self.alert_counter = 0
        self.active_alerts: Dict[str, DistressAlert] = {}
        self.alert_history: list = []
        self.max_history = 100
    
    def create_fall_alert(
        self,
        person_id: int,
        confidence: float,
        bbox: tuple = None,
        duration: float = 0
    ) -> DistressAlert:
        """
        Create a fall detection alert.
        
        Args:
            person_id: ID of fallen person
            confidence: Detection confidence
            bbox: Bounding box of person
            duration: How long person has been down
        
        Returns:
            DistressAlert ready for dispatch
        """
        self.alert_counter += 1
        alert_id = f"FALL-{self.alert_counter:06d}"
        
        gps = self.gps_manager.get_current_position() if self.gps_manager else None
        
        alert = DistressAlert(
            alert_id=alert_id,
            alert_type="fall",
            timestamp=time.time(),
            gps=gps,
            confidence=confidence,
            person_id=person_id,
            additional_data={
                "bbox": bbox,
                "duration_seconds": duration,
                "status": "confirmed" if confidence > 0.8 else "suspected"
            }
        )
        
        self._record_alert(alert)
        return alert
    
    def create_panic_alert(
        self,
        confidence: float,
        affected_area: tuple = None,
        estimated_count: int = 0
    ) -> DistressAlert:
        """Create a panic/stampede detection alert."""
        self.alert_counter += 1
        alert_id = f"PANIC-{self.alert_counter:06d}"
        
        gps = self.gps_manager.get_current_position() if self.gps_manager else None
        
        alert = DistressAlert(
            alert_id=alert_id,
            alert_type="panic",
            timestamp=time.time(),
            gps=gps,
            confidence=confidence,
            person_id=None,
            additional_data={
                "affected_area": affected_area,
                "estimated_people": estimated_count,
                "severity": "high" if confidence > 0.8 else "medium"
            }
        )
        
        self._record_alert(alert)
        return alert
    
    def create_crush_risk_alert(
        self,
        density: float,
        location: tuple = None
    ) -> DistressAlert:
        """Create a crush risk alert."""
        self.alert_counter += 1
        alert_id = f"CRUSH-{self.alert_counter:06d}"
        
        gps = self.gps_manager.get_current_position() if self.gps_manager else None
        
        alert = DistressAlert(
            alert_id=alert_id,
            alert_type="crush_risk",
            timestamp=time.time(),
            gps=gps,
            confidence=min(density / 10.0, 1.0),
            person_id=None,
            additional_data={
                "density": density,
                "frame_location": location,
                "severity": "critical" if density > 8 else "high"
            }
        )
        
        self._record_alert(alert)
        return alert
    
    def _record_alert(self, alert: DistressAlert):
        """Record alert in history."""
        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert)
        
        if len(self.alert_history) > self.max_history:
            self.alert_history.pop(0)
    
    def resolve_alert(self, alert_id: str):
        """Mark an alert as resolved."""
        if alert_id in self.active_alerts:
            del self.active_alerts[alert_id]
    
    def get_active_alerts(self) -> list:
        """Get all active unresolved alerts."""
        return list(self.active_alerts.values())
    
    def get_stats(self) -> Dict:
        """Get alert statistics."""
        return {
            "total_alerts": self.alert_counter,
            "active_alerts": len(self.active_alerts),
            "fall_alerts": sum(1 for a in self.alert_history if a.alert_type == "fall"),
            "panic_alerts": sum(1 for a in self.alert_history if a.alert_type == "panic"),
            "crush_alerts": sum(1 for a in self.alert_history if a.alert_type == "crush_risk")
        }
