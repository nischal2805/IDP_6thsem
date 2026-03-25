"""
Telegram Alert Bot for Crowd Monitoring System.
Sends real-time distress alerts with GPS locations.
"""
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
import time
import json

try:
    from telegram import Bot, Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("Warning: python-telegram-bot not installed")


@dataclass
class AlertConfig:
    """Configuration for alert formatting and routing."""
    fall_emoji: str = "🚨"
    panic_emoji: str = "⚠️"
    crush_emoji: str = "🔴"
    info_emoji: str = "ℹ️"
    
    fall_priority: str = "HIGH"
    panic_priority: str = "CRITICAL"
    crush_priority: str = "CRITICAL"


class TelegramAlertBot:
    """
    Telegram bot for dispatching crowd monitoring alerts.
    
    Features:
    - Real-time distress alerts with GPS links
    - Configurable alert channels
    - Alert acknowledgment tracking
    - Status reporting commands
    """
    
    def __init__(
        self,
        bot_token: str,
        alert_chat_ids: List[int],
        config: AlertConfig = None
    ):
        """
        Initialize Telegram bot.
        
        Args:
            bot_token: Telegram bot API token
            alert_chat_ids: List of chat IDs to send alerts to
            config: Alert configuration
        """
        self.bot_token = bot_token
        self.alert_chat_ids = alert_chat_ids
        self.config = config or AlertConfig()
        
        self.bot: Optional[Bot] = None
        self.application: Optional[Application] = None
        
        # Alert tracking
        self.sent_alerts: Dict[str, Dict] = {}
        self.acknowledged_alerts: set = set()
        
        # Statistics
        self.stats = {
            "total_sent": 0,
            "fall_alerts": 0,
            "panic_alerts": 0,
            "crush_alerts": 0,
            "acknowledged": 0
        }
        
        if TELEGRAM_AVAILABLE:
            self._setup_bot()
    
    def _setup_bot(self):
        """Initialize bot and handlers."""
        self.bot = Bot(token=self.bot_token)
        self.application = Application.builder().token(self.bot_token).build()
        
        # Add command handlers
        self.application.add_handler(CommandHandler("status", self._cmd_status))
        self.application.add_handler(CommandHandler("ack", self._cmd_acknowledge))
        self.application.add_handler(CommandHandler("history", self._cmd_history))
        self.application.add_handler(CommandHandler("help", self._cmd_help))
    
    async def start(self):
        """Start the bot (for standalone mode)."""
        if self.application:
            await self.application.initialize()
            await self.application.start()
            print("Telegram bot started")
    
    async def stop(self):
        """Stop the bot."""
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
    
    async def send_fall_alert(
        self,
        alert_id: str,
        person_id: int,
        confidence: float,
        gps_lat: float = None,
        gps_lng: float = None,
        duration: float = 0,
        additional_info: str = ""
    ) -> bool:
        """
        Send fall detection alert.
        
        Args:
            alert_id: Unique alert identifier
            person_id: ID of fallen person
            confidence: Detection confidence (0-1)
            gps_lat: GPS latitude
            gps_lng: GPS longitude
            duration: Time since fall detected
            additional_info: Extra information
        
        Returns:
            True if sent successfully
        """
        emoji = self.config.fall_emoji
        priority = self.config.fall_priority
        
        message = f"""
{emoji} **FALL DETECTED** {emoji}

🆔 Alert ID: `{alert_id}`
👤 Person ID: {person_id}
📊 Confidence: {confidence:.1%}
⏱️ Duration: {duration:.1f}s
🎯 Priority: {priority}
"""
        
        if gps_lat and gps_lng:
            maps_url = f"https://maps.google.com/?q={gps_lat},{gps_lng}"
            message += f"""
📍 **Location:**
   Lat: {gps_lat:.6f}
   Lng: {gps_lng:.6f}
   [Open in Maps]({maps_url})
"""
        
        if additional_info:
            message += f"\nℹ️ {additional_info}"
        
        message += f"\n\n_Reply with /ack {alert_id} to acknowledge_"
        
        success = await self._broadcast_message(message)
        
        if success:
            self.stats["total_sent"] += 1
            self.stats["fall_alerts"] += 1
            self.sent_alerts[alert_id] = {
                "type": "fall",
                "timestamp": time.time(),
                "person_id": person_id
            }
        
        return success
    
    async def send_panic_alert(
        self,
        alert_id: str,
        confidence: float,
        affected_count: int,
        gps_lat: float = None,
        gps_lng: float = None,
        severity: str = "HIGH"
    ) -> bool:
        """Send panic/stampede detection alert."""
        emoji = self.config.panic_emoji
        priority = self.config.panic_priority
        
        message = f"""
{emoji} **PANIC/STAMPEDE DETECTED** {emoji}

🆔 Alert ID: `{alert_id}`
📊 Confidence: {confidence:.1%}
👥 Affected: ~{affected_count} people
🔥 Severity: {severity}
🎯 Priority: {priority}
"""
        
        if gps_lat and gps_lng:
            maps_url = f"https://maps.google.com/?q={gps_lat},{gps_lng}"
            message += f"""
📍 **Location:**
   [Open in Maps]({maps_url})
"""
        
        message += """
⚡ **Recommended Actions:**
• Alert security personnel
• Prepare crowd control measures
• Monitor exit routes
"""
        
        message += f"\n_Reply with /ack {alert_id} to acknowledge_"
        
        success = await self._broadcast_message(message)
        
        if success:
            self.stats["total_sent"] += 1
            self.stats["panic_alerts"] += 1
            self.sent_alerts[alert_id] = {
                "type": "panic",
                "timestamp": time.time(),
                "severity": severity
            }
        
        return success
    
    async def send_crush_risk_alert(
        self,
        alert_id: str,
        density: float,
        location_desc: str = "",
        gps_lat: float = None,
        gps_lng: float = None
    ) -> bool:
        """Send crush risk alert."""
        emoji = self.config.crush_emoji
        priority = self.config.crush_priority
        
        severity = "CRITICAL" if density > 8 else "HIGH"
        
        message = f"""
{emoji} **CRUSH RISK DETECTED** {emoji}

🆔 Alert ID: `{alert_id}`
📊 Density: {density:.1f} people/m²
🔥 Severity: {severity}
🎯 Priority: {priority}
"""
        
        if location_desc:
            message += f"📍 Area: {location_desc}\n"
        
        if gps_lat and gps_lng:
            maps_url = f"https://maps.google.com/?q={gps_lat},{gps_lng}"
            message += f"🗺️ [View on Maps]({maps_url})\n"
        
        message += """
⚡ **IMMEDIATE ACTIONS REQUIRED:**
• Stop further entry to area
• Open additional exit routes
• Deploy crowd control
• Prepare medical response
"""
        
        message += f"\n_Reply with /ack {alert_id} to acknowledge_"
        
        success = await self._broadcast_message(message)
        
        if success:
            self.stats["total_sent"] += 1
            self.stats["crush_alerts"] += 1
            self.sent_alerts[alert_id] = {
                "type": "crush",
                "timestamp": time.time(),
                "density": density
            }
        
        return success
    
    async def send_status_update(
        self,
        crowd_count: int,
        density_forecast: Dict,
        active_alerts: int
    ) -> bool:
        """Send periodic status update."""
        emoji = self.config.info_emoji
        
        trend_emoji = "📈" if density_forecast.get("trend") == "increasing" else \
                      "📉" if density_forecast.get("trend") == "decreasing" else "➡️"
        
        message = f"""
{emoji} **System Status Update** {emoji}

👥 Current Count: {crowd_count}
{trend_emoji} Trend: {density_forecast.get("trend", "unknown")}

📊 **Density Forecast:**
   10s: {density_forecast.get("10s", "N/A")}
   30s: {density_forecast.get("30s", "N/A")}
   60s: {density_forecast.get("60s", "N/A")}

🚨 Active Alerts: {active_alerts}
"""
        
        if density_forecast.get("warning"):
            message += f"\n⚠️ {density_forecast['warning']}"
        
        return await self._broadcast_message(message)
    
    async def _broadcast_message(self, message: str) -> bool:
        """Send message to all configured chat IDs."""
        if not TELEGRAM_AVAILABLE or not self.bot:
            print(f"[TELEGRAM MOCK] {message[:100]}...")
            return True
        
        success = True
        for chat_id in self.alert_chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Failed to send to {chat_id}: {e}")
                success = False
        
        return success
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        status = f"""
📊 **Alert Bot Status**

📨 Total Alerts Sent: {self.stats['total_sent']}
🚨 Fall Alerts: {self.stats['fall_alerts']}
⚠️ Panic Alerts: {self.stats['panic_alerts']}
🔴 Crush Alerts: {self.stats['crush_alerts']}
✅ Acknowledged: {self.stats['acknowledged']}

🔔 Pending Acknowledgment: {len(self.sent_alerts) - len(self.acknowledged_alerts)}
"""
        await update.message.reply_text(status, parse_mode="Markdown")
    
    async def _cmd_acknowledge(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ack command."""
        if not context.args:
            await update.message.reply_text("Usage: /ack <alert_id>")
            return
        
        alert_id = context.args[0]
        
        if alert_id in self.sent_alerts and alert_id not in self.acknowledged_alerts:
            self.acknowledged_alerts.add(alert_id)
            self.stats["acknowledged"] += 1
            await update.message.reply_text(f"✅ Alert `{alert_id}` acknowledged!", parse_mode="Markdown")
        elif alert_id in self.acknowledged_alerts:
            await update.message.reply_text(f"Alert `{alert_id}` already acknowledged.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"Unknown alert ID: `{alert_id}`", parse_mode="Markdown")
    
    async def _cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command."""
        if not self.sent_alerts:
            await update.message.reply_text("No alerts in history.")
            return
        
        history = "📜 **Recent Alerts:**\n\n"
        for alert_id, info in list(self.sent_alerts.items())[-10:]:
            ack_status = "✅" if alert_id in self.acknowledged_alerts else "⏳"
            history += f"{ack_status} `{alert_id}` - {info['type']}\n"
        
        await update.message.reply_text(history, parse_mode="Markdown")
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = """
🤖 **Crowd Monitoring Alert Bot**

**Commands:**
/status - View bot and alert statistics
/ack <alert_id> - Acknowledge an alert
/history - View recent alerts
/help - Show this help message

**Alert Types:**
🚨 Fall Detection - Person fallen
⚠️ Panic/Stampede - Crowd panic detected
🔴 Crush Risk - Dangerous density

Alerts include GPS links when available.
"""
        await update.message.reply_text(help_text, parse_mode="Markdown")


class MockTelegramBot:
    """Mock bot for testing without Telegram credentials."""
    
    def __init__(self):
        self.messages: List[str] = []
    
    async def send_fall_alert(self, **kwargs) -> bool:
        self.messages.append(f"FALL: {kwargs}")
        print(f"[MOCK TELEGRAM] Fall alert: {kwargs.get('alert_id')}")
        return True
    
    async def send_panic_alert(self, **kwargs) -> bool:
        self.messages.append(f"PANIC: {kwargs}")
        print(f"[MOCK TELEGRAM] Panic alert: {kwargs.get('alert_id')}")
        return True
    
    async def send_crush_risk_alert(self, **kwargs) -> bool:
        self.messages.append(f"CRUSH: {kwargs}")
        print(f"[MOCK TELEGRAM] Crush alert: {kwargs.get('alert_id')}")
        return True
    
    async def send_status_update(self, **kwargs) -> bool:
        print(f"[MOCK TELEGRAM] Status update: count={kwargs.get('crowd_count')}")
        return True
