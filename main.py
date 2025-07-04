from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from typing import List, Optional, Dict
from contextlib import asynccontextmanager
from datetime import datetime
import os

from models import (
    PumpInfo,
    PumpStatusResponse,
    PumpDiscoveryResult,
    CommandRequest,
    CommandResponse,
)
from pump_manager import PumpManager


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/logs.log", mode="a")],
)

logging.getLogger("GilbarcoAPI").setLevel(logging.INFO)
logging.getLogger("GilbarcoStartup").setLevel(logging.INFO)
logging.getLogger("PumpManager").setLevel(logging.INFO)
logging.getLogger("TwoWireManager").setLevel(logging.DEBUG)
logging.getLogger("SerialConnection").setLevel(logging.DEBUG)
logging.getLogger("uvicorn").setLevel(logging.INFO)

logger = logging.getLogger("GilbarcoAPI")
startup_logger = logging.getLogger("GilbarcoStartup")

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
    startup_logger.info(f"Swagger UI: http://localhost:{settings.API_PORT}/docs")

    yield

    startup_logger.info("=== Shutting down Gilbarco SK700-II Control System ===")
    if pump_manager:
        startup_logger.info("Shutting down Pump Manager...")
        pump_manager.shutdown()
        startup_logger.info("Pump Manager shutdown complete")
    startup_logger.info("System shutdown complete")


app = FastAPI(
    title="Gilbarco SK700-II Control API",
    description="""
    API for controlling Gilbarco SK700-II fuel dispensers
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_tags=[
        {"name": "Health", "description": "API health and system status endpoints"},
        {
            "name": "Pump Discovery",
            "description": "Discover and scan for pumps on COM ports",
        },
        {
            "name": "Pump Management",
            "description": "Add, remove, and configure pumps in the system",
        },
        {
            "name": "Pump Information",
            "description": "Get pump information and real-time status",
        },
        {
            "name": "Pump Control",
            "description": "Execute commands on pumps (extensible for future features)",
        },
        {
            "name": "Port Control",
            "description": "Connect and disconnect COM ports (Two-Wire Protocol)",
        },
        {
            "name": "Debug",
            "description": "Debug and monitoring endpoints for troubleshooting",
        },
    ],
)

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


@app.get(
    "/api/health",
    tags=["Health"],
    summary="Health Check",
    description="Check if the API is running and healthy. Returns system status and pump count.",
)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Gilbarco SK700-II Control API",
        "version": "1.0.0",
        "pumps_managed": len(pump_manager.pumps) if pump_manager else 0,
    }


@app.post(
    "/api/pumps/discover",
    response_model=PumpDiscoveryResult,
    tags=["Pump Discovery"],
    summary="Discover Pumps",
    description="""
          Scan COM ports to discover connected Gilbarco SK700-II pumps.
          
          Parameters:
          - min_address: Starting pump address to test (1-16)
          - max_address: Ending pump address to test (1-16) 
          - timeout: Timeout in seconds for each pump test
          
          Returns: Discovery results with found pumps
          """,
)
async def discover_pumps(
    address_range_start: int = Query(
        1, ge=1, le=99, description="Start of pump address range to test"
    ),
    address_range_end: int = Query(
        16, ge=1, le=99, description="End of pump address range to test"
    ),
    timeout: float = Query(
        1.0, gt=0, le=10, description="Timeout in seconds for each pump test"
    ),
):
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")

    try:
        if address_range_start > address_range_end:
            raise HTTPException(
                status_code=400,
                detail="address_range_start must be less than or equal to address_range_end",
            )

        result = pump_manager.auto_discover_and_manage(
            com_ports=[os.getenv("COM_PORT", "")],
            address_range=(address_range_start, address_range_end),
            timeout=timeout,
        )

        return result

    except Exception as e:
        logger.error(f"Error during pump discovery: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@app.get(
    "/api/pumps",
    response_model=List[PumpInfo],
    tags=["Pump Management"],
    summary="Get All Pumps",
    description="Get information about all managed pumps in the system.",
)
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


@app.get(
    "/api/pumps/{pump_id}",
    response_model=PumpInfo,
    tags=["Pump Management"],
    summary="Get Pump Info",
    description="Get detailed information about a specific pump by ID.",
)
async def get_pump_info(pump_id: int = Path(..., description="Pump ID", ge=1)):
    """Get information about a specific pump by ID"""
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")

    pumps = pump_manager.get_pump_list()
    for pump in pumps:
        if pump.pump_id == pump_id:
            return pump

    raise HTTPException(status_code=404, detail=f"Pump {pump_id} not found")


@app.get(
    "/api/pumps/{pump_id}/status",
    response_model=PumpStatusResponse,
    tags=["Pump Information"],
    summary="Get Pump Status",
    description="""
         Get real-time status of a specific pump.
         
         Returns:
         - Current pump status (IDLE, CALLING, AUTHORIZED, DISPENSING, etc.)
         - Connection status
         - Last communication timestamp
         - Current transaction data (if any)
         """,
)
async def get_pump_status(pump_id: int = Path(..., description="Pump ID", ge=1)):
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


@app.get(
    "/api/pumps/status",
    response_model=Dict[int, PumpStatusResponse],
    tags=["Pump Information"],
    summary="Get All Pump Statuses",
    description="Get the current status of all managed pumps in parallel.",
)
async def get_all_pump_statuses():
    """
    Get the current status of all managed pumps.

    This endpoint queries all pumps in parallel for better performance.
    Returns a dictionary mapping pump IDs to their status information.
    """
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")

    return pump_manager.get_all_pump_statuses()


@app.post(
    "/api/ports/{com_port}/connect",
    tags=["Port Control"],
    summary="Connect to COM Port",
    description="Establish serial connection to a specific COM port (all pumps on that port).",
)
async def connect_port(
    com_port: str = Path(..., description="COM port (e.g., COM1, /dev/ttyUSB0)")
):
    """Connect to a specific COM port"""
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")

    success = pump_manager.connect_port(com_port)
    if not success:
        raise HTTPException(
            status_code=400, detail=f"Failed to connect to COM port {com_port}"
        )

    return {"message": f"Successfully connected to COM port {com_port}"}


@app.post(
    "/api/ports/{com_port}/disconnect",
    tags=["Port Control"],
    summary="Disconnect from COM Port",
    description="Disconnect from a specific COM port (all pumps on that port).",
)
async def disconnect_port(
    com_port: str = Path(..., description="COM port (e.g., COM1, /dev/ttyUSB0)")
):
    """Disconnect from a specific COM port"""
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")

    success = pump_manager.disconnect_port(com_port)
    if not success:
        raise HTTPException(
            status_code=404, detail=f"COM port {com_port} not found or not connected"
        )

    return {"message": f"Successfully disconnected from COM port {com_port}"}


@app.post(
    "/api/ports/connect-all",
    tags=["Port Control"],
    summary="Connect to All COM Ports",
    description="Connect to all COM ports used by managed pumps.",
)
async def connect_all_ports():
    """Connect to all COM ports used by managed pumps"""
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")

    results = pump_manager.connect_all_ports()

    return {
        "message": "Connection attempt completed for all COM ports",
        "results": results,
        "successful_connections": sum(1 for success in results.values() if success),
        "total_ports": len(results),
    }


@app.post(
    "/api/ports/disconnect-all",
    tags=["Port Control"],
    summary="Disconnect from All COM Ports",
    description="Disconnect from all COM ports used by managed pumps.",
)
async def disconnect_all_ports():
    """Disconnect from all COM ports"""
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")

    pump_manager.disconnect_all_ports()

    return {"message": "Successfully disconnected from all COM ports"}


@app.get(
    "/api/ports/connected",
    tags=["Port Control"],
    summary="Get Connected COM Ports",
    description="Get a list of currently connected COM ports.",
)
async def get_connected_ports():
    """Get list of currently connected COM ports"""
    if not pump_manager:
        raise HTTPException(status_code=500, detail="Pump manager not initialized")

    connected_ports = pump_manager.get_connected_ports()

    return {"connected_ports": connected_ports, "total_connected": len(connected_ports)}


# Future command endpoints (placeholder for extensibility)
@app.post(
    "/api/pumps/{pump_id}/commands",
    tags=["Pump Control"],
    response_model=CommandResponse,
    summary="Execute Command",
    description="Execute a custom command on a pump (extensible for future commands)",
)
async def execute_command(
    pump_id: int = Path(..., description="Pump ID", ge=1),
    command_request: CommandRequest = ...,
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
        timestamp=datetime.now(),
    )


# Debug and Monitoring Endpoints
@app.get("/debug/logging", tags=["Debug"])
async def get_logging_config():
    """Get current logging configuration"""
    loggers = {
        "GilbarcoAPI": logging.getLogger("GilbarcoAPI").level,
        "PumpManager": logging.getLogger("PumpManager").level,
        "TwoWireManager": logging.getLogger("TwoWireManager").level,
        "SerialConnection": logging.getLogger("SerialConnection").level,
        "uvicorn": logging.getLogger("uvicorn").level,
    }

    level_names = {10: "DEBUG", 20: "INFO", 30: "WARNING", 40: "ERROR", 50: "CRITICAL"}

    return {
        "loggers": {
            name: level_names.get(level, level) for name, level in loggers.items()
        },
        "log_file": "logs/logs.log",
        "timestamp": datetime.now(),
    }


@app.post("/debug/logging/{logger_name}/{level}", tags=["Debug"])
async def set_logging_level(
    logger_name: str = Path(
        ..., description="Logger name (e.g., TwoWireManager, SerialConnection)"
    ),
    level: str = Path(
        ..., description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
):
    """Set logging level for specific logger at runtime"""
    try:
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        if level.upper() not in level_map:
            raise HTTPException(status_code=400, detail=f"Invalid level: {level}")

        target_logger = logging.getLogger(logger_name)
        old_level = target_logger.level
        target_logger.setLevel(level_map[level.upper()])

        logger.info(
            f"Changed {logger_name} log level from {old_level} to {level_map[level.upper()]}"
        )

        return {
            "logger": logger_name,
            "old_level": old_level,
            "new_level": level_map[level.upper()],
            "timestamp": datetime.now(),
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

        pump_info = pump_manager.get_pump_info(pump_id)
        if not pump_info:
            raise HTTPException(status_code=404, detail=f"Pump {pump_id} not found")

        # Get the manager for this pump's COM port
        manager = pump_manager.managers.get(pump_info.com_port)
        connection_info = {}

        if manager:
            connection_info = {
                "is_connected": manager.connection.is_connected,
                "com_port": manager.connection.com_port,
                "baudrate": manager.connection.baudrate,
                "timeout": manager.connection.timeout,
            }

        return {
            "pump_id": pump_id,
            "pump_info": {
                "name": pump_info.name,
                "com_port": pump_info.com_port,
                "address": pump_info.address,
                "is_connected": pump_info.is_connected,
            },
            "connection_status": connection_info,
            "manager_exists": manager is not None,
            "timestamp": datetime.now(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting debug info for pump {pump_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
