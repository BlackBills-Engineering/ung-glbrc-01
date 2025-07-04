from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime


class PumpStatus(str, Enum):
    """    
    Protocol Status Codes:
    - 0x0: Data Error → ERROR
    - 0x6: Off → IDLE  
    - 0x7: Call → CALLING
    - 0x8: Authorized/Not Delivering → AUTHORIZED
    - 0x9: Busy → DISPENSING
    - 0xA: Transaction Complete (PEOT) → COMPLETE
    - 0xB: Transaction Complete (FEOT) → COMPLETE  
    - 0xC: Pump Stop → STOPPED
    - 0xD: Send Data → ERROR (special state)
    """
    IDLE = "IDLE"                    # Pump is off/ready (protocol 0x6)
    CALLING = "CALLING"              # Customer requesting service (protocol 0x7)
    AUTHORIZED = "AUTHORIZED"        # Pump authorized but not dispensing (protocol 0x8)
    DISPENSING = "DISPENSING"        # Actively dispensing fuel (protocol 0x9)
    COMPLETE = "COMPLETE"            # Transaction finished (protocol 0xA/0xB)
    STOPPED = "STOPPED"              # Emergency stop activated (protocol 0xC)
    ERROR = "ERROR"                  # Communication/data error (protocol 0x0/0xD)
    OFFLINE = "OFFLINE"              # No communication with pump


class PumpInfo(BaseModel):
    """Basic pump information"""
    pump_id: int = Field(..., description="Pump identifier")
    com_port: str = Field(..., description="COM port connection")
    address: int = Field(..., description="Pump address on serial line")
    name: Optional[str] = Field(None, description="Pump display name")
    is_connected: bool = Field(False, description="Connection status")


class PumpStatusResponse(BaseModel):
    """
    Pump status response with detailed protocol information
    
    Example:
    {
        "pump_id": 1,
        "status": "AUTHORIZED", 
        "last_updated": "2025-07-05T12:34:56.789Z",
        "error_message": null,
        "raw_status_code": "0x8",
        "wire_format": "0x81"
    }
    """
    pump_id: int = Field(..., description="Pump identifier (1-16)")
    status: PumpStatus = Field(..., description="Current pump status")
    last_updated: datetime = Field(..., description="Last status update timestamp")
    error_message: Optional[str] = Field(None, description="Error details if status is ERROR")
    raw_status_code: Optional[str] = Field(None, description="Raw protocol status code (hex)")
    wire_format: Optional[str] = Field(None, description="Complete wire format byte (hex)")
    
    
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
