import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from pump_manager import PumpManager
from models import PumpInfo, PumpStatus


class PumpMonitor:
    """Monitors pump status and provides alerts/notifications"""
    
    def __init__(self, pump_manager: PumpManager, check_interval: int = 30):
        self.pump_manager = pump_manager
        self.check_interval = check_interval
        self.monitoring = False
        self.status_history: Dict[int, List[Dict]] = {}
        self.alert_callbacks = []
        self.logger = logging.getLogger("PumpMonitor")
    
    def add_alert_callback(self, callback):
        """Add callback function for alerts"""
        self.alert_callbacks.append(callback)
    
    async def start_monitoring(self):
        """Start monitoring pump statuses"""
        self.monitoring = True
        self.logger.info("Starting pump monitoring...")
        
        while self.monitoring:
            await self._check_all_pumps()
            await asyncio.sleep(self.check_interval)
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        self.logger.info("Stopping pump monitoring...")
    
    async def _check_all_pumps(self):
        """Check status of all pumps"""
        try:
            statuses = self.pump_manager.get_all_pump_statuses()
            
            for pump_id, status in statuses.items():
                self._update_status_history(pump_id, status)
                await self._check_for_alerts(pump_id, status)
                
        except Exception as e:
            self.logger.error(f"Error during pump monitoring: {str(e)}")
    
    def _update_status_history(self, pump_id: int, status):
        """Update status history for a pump"""
        if pump_id not in self.status_history:
            self.status_history[pump_id] = []
        
        # Keep last 100 status updates
        history = self.status_history[pump_id]
        history.append({
            "timestamp": datetime.now(),
            "status": status.status,
            "error_message": status.error_message
        })
        
        if len(history) > 100:
            history.pop(0)
    
    async def _check_for_alerts(self, pump_id: int, status):
        """Check for alert conditions"""
        # Alert on error status
        if status.status == PumpStatus.ERROR:
            await self._send_alert(
                pump_id, 
                "ERROR", 
                f"Pump {pump_id} has error status: {status.error_message}"
            )
        
        # Alert on offline status
        elif status.status == PumpStatus.OFFLINE:
            await self._send_alert(
                pump_id,
                "OFFLINE",
                f"Pump {pump_id} is offline"
            )
        
        # Alert on stuck status (same status for too long)
        history = self.status_history.get(pump_id, [])
        if len(history) >= 5:
            recent_statuses = [h["status"] for h in history[-5:]]
            if all(s == recent_statuses[0] for s in recent_statuses) and recent_statuses[0] == PumpStatus.DISPENSING:
                await self._send_alert(
                    pump_id,
                    "STUCK",
                    f"Pump {pump_id} has been dispensing for an unusually long time"
                )
    
    async def _send_alert(self, pump_id: int, alert_type: str, message: str):
        """Send alert to all registered callbacks"""
        alert_data = {
            "pump_id": pump_id,
            "type": alert_type,
            "message": message,
            "timestamp": datetime.now()
        }
        
        self.logger.warning(f"ALERT: {message}")
        
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert_data)
                else:
                    callback(alert_data)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {str(e)}")
    
    def get_pump_history(self, pump_id: int, hours: int = 24) -> List[Dict]:
        """Get status history for a pump"""
        if pump_id not in self.status_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        history = self.status_history[pump_id]
        
        return [
            h for h in history 
            if h["timestamp"] >= cutoff_time
        ]
