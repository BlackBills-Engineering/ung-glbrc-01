from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import uvicorn
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from datetime import datetime

from models import (
    PumpInfo, PumpStatusResponse, PumpDiscoveryResult, 
    CommandRequest, CommandResponse, ErrorResponse
)
from pump_manager import PumpManager


# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('gilbarco_system.log', mode='a')
    ]
)

# Set logger levels for different components
logging.getLogger("GilbarcoAPI").setLevel(logging.INFO)
logging.getLogger("GilbarcoStartup").setLevel(logging.INFO)
logging.getLogger("PumpManager").setLevel(logging.INFO)
logging.getLogger("PumpController").setLevel(logging.DEBUG)
logging.getLogger("SerialConnection").setLevel(logging.DEBUG)
logging.getLogger("uvicorn").setLevel(logging.INFO)

logger = logging.getLogger("GilbarcoAPI")
startup_logger = logging.getLogger("GilbarcoStartup")

# Global pump manager instance
pump_manager: Optional[PumpManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global pump_manager
    
    # Startup
    startup_logger.info("=== Starting Gilbarco SK700-II Control System ===")
    startup_logger.info(f"Startup time: {datetime.now()}")
    
    # Load configuration
    from config import settings
    startup_logger.info(f"Configuration: {settings.dict()}")
    
    # Initialize pump manager
    startup_logger.info("Initializing Pump Manager...")
    pump_manager = PumpManager()
    startup_logger.info("Pump Manager initialized successfully")
    
    startup_logger.info("System startup complete - API ready to serve requests")
    startup_logger.info("Swagger UI: http://localhost:8000/docs")
    startup_logger.info("ReDoc: http://localhost:8000/redoc")
    
    yield
    
    # Shutdown
    startup_logger.info("=== Shutting down Gilbarco SK700-II Control System ===")
    if pump_manager:
        startup_logger.info("Shutting down Pump Manager...")
        pump_manager.shutdown()
        startup_logger.info("Pump Manager shutdown complete")
    startup_logger.info("System shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Gilbarco SK700-II Control API",
    description="RESTful API for controlling Gilbarco SK700-II fuel dispensers",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def root():
    """Redirect to API documentation"""
    return RedirectResponse(url="/docs")


@app.get("/api/health", 
         summary="Health Check",
         description="Check if the API is running and healthy")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Gilbarco SK700-II Control API",
        "version": "1.0.0",
        "pumps_managed": len(pump_manager.pumps) if pump_manager else 0
    }


@app.post("/api/pumps/discover",
          response_model=PumpDiscoveryResult,
          summary="Discover Pumps",
          description="Scan COM ports to discover connected Gilbarco SK700-II pumps")
async def discover_pumps(
    com_ports: Optional[List[str]] = Query(
        None, 
        description="List of COM ports to scan (e.g., ['COM1', 'COM2']). If not provided, all available ports will be scanned"
    ),
    address_range_start: int = Query(
        1, 
        ge=1, 
        le=99, 
        description="Start of pump address range to test"
    ),
    address_range_end: int = Query(
        16, 
        ge=1, 
        le=99, 
        description="End of pump address range to test"
    ),
    timeout: float = Query(
        2.0, 
        gt=0, 
        le=10, 
        description="Timeout in seconds for each pump test"
    )
):
    """
    Discover pumps by scanning COM ports and testing pump addresses.
    
    This endpoint will:
    1. Scan specified COM ports (or all available if not specified)
    2. Test each pump address in the specified range
    3. Return information about discovered pumps
    
    **Note:** This operation may take some time depending on the number of ports and address range.
    """
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")
    
    try:
        if address_range_start > address_range_end:
            raise HTTPException(
                status_code=400, 
                detail="address_range_start must be less than or equal to address_range_end"
            )
        
        result = pump_manager.discover_pumps(
            com_ports=com_ports,
            address_range=(address_range_start, address_range_end),
            timeout=timeout
        )
        
        # Automatically add discovered pumps to management
        for pump_info in result.discovered_pumps:
            pump_manager.add_pump(pump_info)
        
        return result
        
    except Exception as e:
        logger.error(f"Error during pump discovery: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@app.get("/api/pumps",
         response_model=List[PumpInfo],
         summary="Get All Pumps",
         description="Get information about all managed pumps")
async def get_all_pumps():
    """
    Get a list of all pumps currently managed by the system.
    
    Returns basic information about each pump including:
    - Pump ID
    - COM port
    - Address
    - Connection status
    """
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")
    
    return pump_manager.get_pump_list()


@app.get("/api/pumps/{pump_id}",
         response_model=PumpInfo,
         summary="Get Pump Info",
         description="Get information about a specific pump")
async def get_pump_info(
    pump_id: int = Path(..., description="Pump ID", ge=1)
):
    """Get information about a specific pump by ID"""
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")
    
    pumps = pump_manager.get_pump_list()
    for pump in pumps:
        if pump.pump_id == pump_id:
            return pump
    
    raise HTTPException(status_code=404, detail=f"Pump {pump_id} not found")


@app.get("/api/pumps/{pump_id}/status",
         response_model=PumpStatusResponse,
         summary="Get Pump Status",
         description="Get the current status of a specific pump")
async def get_pump_status(
    pump_id: int = Path(..., description="Pump ID", ge=1)
):
    """
    Get the current status of a specific pump.
    
    Returns:
    - Current pump status (IDLE, DISPENSING, COMPLETE, etc.)
    - Last update timestamp
    - Error message if applicable
    """
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")
    
    status = pump_manager.get_pump_status(pump_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Pump {pump_id} not found")
    
    return status


@app.get("/api/pumps/status",
         response_model=Dict[int, PumpStatusResponse],
         summary="Get All Pump Statuses",
         description="Get the current status of all managed pumps")
async def get_all_pump_statuses():
    """
    Get the current status of all managed pumps.
    
    This endpoint queries all pumps in parallel for better performance.
    Returns a dictionary mapping pump IDs to their status information.
    """
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")
    
    return pump_manager.get_all_pump_statuses()


@app.post("/api/pumps/{pump_id}/connect",
          summary="Connect to Pump",
          description="Establish connection to a specific pump")
async def connect_pump(
    pump_id: int = Path(..., description="Pump ID", ge=1)
):
    """Connect to a specific pump"""
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")
    
    success = pump_manager.connect_pump(pump_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Pump {pump_id} not found or connection failed")
    
    return {"message": f"Successfully connected to pump {pump_id}"}


@app.post("/api/pumps/{pump_id}/disconnect",
          summary="Disconnect from Pump",
          description="Disconnect from a specific pump")
async def disconnect_pump(
    pump_id: int = Path(..., description="Pump ID", ge=1)
):
    """Disconnect from a specific pump"""
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")
    
    success = pump_manager.disconnect_pump(pump_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Pump {pump_id} not found")
    
    return {"message": f"Successfully disconnected from pump {pump_id}"}


@app.post("/api/pumps/connect-all",
          summary="Connect to All Pumps",
          description="Connect to all managed pumps")
async def connect_all_pumps():
    """Connect to all managed pumps"""
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")
    
    results = pump_manager.connect_all_pumps()
    
    return {
        "message": "Connection attempt completed for all pumps",
        "results": results,
        "successful_connections": sum(1 for success in results.values() if success),
        "total_pumps": len(results)
    }


@app.post("/api/pumps/disconnect-all",
          summary="Disconnect from All Pumps",
          description="Disconnect from all managed pumps")
async def disconnect_all_pumps():
    """Disconnect from all managed pumps"""
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")
    
    pump_manager.disconnect_all_pumps()
    
    return {"message": "Successfully disconnected from all pumps"}


@app.delete("/api/pumps/{pump_id}",
           summary="Remove Pump",
           description="Remove a pump from management")
async def remove_pump(
    pump_id: int = Path(..., description="Pump ID", ge=1)
):
    """Remove a pump from management"""
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")
    
    success = pump_manager.remove_pump(pump_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Pump {pump_id} not found")
    
    return {"message": f"Successfully removed pump {pump_id}"}


# Future command endpoints (placeholder for extensibility)
@app.post("/api/pumps/{pump_id}/commands",
          response_model=CommandResponse,
          summary="Execute Command",
          description="Execute a custom command on a pump (extensible for future commands)")
async def execute_command(
    pump_id: int = Path(..., description="Pump ID", ge=1),
    command_request: CommandRequest = ...
):
    """
    Execute a custom command on a pump.
    
    This endpoint provides extensibility for future command implementations.
    Currently supported commands can be added here.
    """
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")
    
    if pump_id not in pump_manager.pumps:
        raise HTTPException(status_code=404, detail=f"Pump {pump_id} not found")
    
    # Placeholder for future command implementations
    return CommandResponse(
        success=False,
        message=f"Command '{command_request.command}' not yet implemented",
        data=None,
        timestamp=datetime.now()
    )


# Debug and Monitoring Endpoints
@app.get("/debug/logging", tags=["Debug"])
async def get_logging_config():
    """Get current logging configuration"""
    loggers = {
        "GilbarcoAPI": logging.getLogger("GilbarcoAPI").level,
        "PumpManager": logging.getLogger("PumpManager").level,
        "PumpController": logging.getLogger("PumpController").level,
        "SerialConnection": logging.getLogger("SerialConnection").level,
        "uvicorn": logging.getLogger("uvicorn").level,
    }
    
    level_names = {
        10: "DEBUG",
        20: "INFO", 
        30: "WARNING",
        40: "ERROR",
        50: "CRITICAL"
    }
    
    return {
        "loggers": {name: level_names.get(level, level) for name, level in loggers.items()},
        "log_file": "gilbarco_system.log",
        "timestamp": datetime.now()
    }

@app.post("/debug/logging/{logger_name}/{level}", tags=["Debug"])
async def set_logging_level(
    logger_name: str = Path(..., description="Logger name (e.g., PumpController, SerialConnection)"),
    level: str = Path(..., description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
):
    """Set logging level for specific logger at runtime"""
    try:
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        
        if level.upper() not in level_map:
            raise HTTPException(status_code=400, detail=f"Invalid level: {level}")
        
        target_logger = logging.getLogger(logger_name)
        old_level = target_logger.level
        target_logger.setLevel(level_map[level.upper()])
        
        logger.info(f"Changed {logger_name} log level from {old_level} to {level_map[level.upper()]}")
        
        return {
            "logger": logger_name,
            "old_level": old_level,
            "new_level": level_map[level.upper()],
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"Error setting log level: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/communication/{pump_id}", tags=["Debug"])
async def get_communication_debug(pump_id: int):
    """Get detailed communication debug info for a pump"""
    try:
        if not pump_manager:
            raise HTTPException(status_code=500, detail="Pump manager not initialized")
        
        pump_controller = pump_manager.pumps.get(pump_id)
        if not pump_controller:
            raise HTTPException(status_code=404, detail=f"Pump {pump_id} not found")
        
        connection = pump_controller.connection
        pump_info = pump_controller.pump_info
        
        return {
            "pump_id": pump_id,
            "pump_info": {
                "name": pump_info.name,
                "com_port": pump_info.com_port,
                "address": pump_info.address,
                "is_connected": pump_info.is_connected
            },
            "connection_status": {
                "is_connected": connection.is_connected,
                "com_port": connection.com_port,
                "baudrate": connection.baudrate,
                "timeout": connection.timeout
            },
            "last_status": {
                "status": pump_controller.last_status.value if pump_controller.last_status else None,
                "last_update": pump_controller.last_status_update.isoformat() if pump_controller.last_status_update else None
            },
            "timestamp": datetime.now()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting debug info for pump {pump_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
