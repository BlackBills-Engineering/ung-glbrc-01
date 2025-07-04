from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime


class PumpStatus(str, Enum):
    """Pump status enumeration"""
    IDLE = "IDLE"
    DISPENSING = "DISPENSING" 
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"
    CALLING = "CALLING"
    AUTHORIZED = "AUTHORIZED"
    STOPPED = "STOPPED"


class PumpInfo(BaseModel):
    """Basic pump information"""
    pump_id: int = Field(..., description="Pump identifier")
    com_port: str = Field(..., description="COM port connection")
    address: int = Field(..., description="Pump address on serial line")
    name: Optional[str] = Field(None, description="Pump display name")
    is_connected: bool = Field(False, description="Connection status")


class PumpStatusResponse(BaseModel):
    """Pump status response"""
    pump_id: int = Field(..., description="Pump identifier")
    status: PumpStatus = Field(..., description="Current pump status")
    last_updated: datetime = Field(..., description="Last status update time")
    error_message: Optional[str] = Field(None, description="Error message if status is ERROR")
    
    
class TransactionData(BaseModel):
    """Transaction data from pump"""
    pump_id: int = Field(..., description="Pump identifier")
    volume: Optional[float] = Field(None, description="Dispensed volume")
    price_per_unit: Optional[float] = Field(None, description="Price per unit")
    total_amount: Optional[float] = Field(None, description="Total transaction amount")
    grade: Optional[int] = Field(None, description="Fuel grade")
    timestamp: datetime = Field(..., description="Transaction timestamp")


class CommandRequest(BaseModel):
    """Generic command request"""
    pump_id: int = Field(..., description="Target pump identifier")
    command: str = Field(..., description="Command to execute")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Command parameters")


class CommandResponse(BaseModel):
    """Generic command response"""
    success: bool = Field(..., description="Command execution success")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    timestamp: datetime = Field(..., description="Response timestamp")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    timestamp: datetime = Field(..., description="Error timestamp")


class PumpDiscoveryResult(BaseModel):
    """Pump discovery result"""
    discovered_pumps: List[PumpInfo] = Field(..., description="List of discovered pumps")
    total_found: int = Field(..., description="Total number of pumps found")
    scan_duration: float = Field(..., description="Discovery scan duration in seconds")
    timestamp: datetime = Field(..., description="Discovery timestamp")
