from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import uvicorn
from typing import List, Optional
from datetime import datetime

from models import (
    PumpInfo, 
    PumpStatusResponse, 
    PumpDiscoveryResult,
    CommandRequest,
    CommandResponse,
    ErrorResponse
)
from pump_manager import PumpManager

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,  # More detailed logging
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs.log')
    ]
)

# Set specific logger levels for different components
logging.getLogger("API").setLevel(logging.INFO)
logging.getLogger("PumpManager").setLevel(logging.INFO) 
logging.getLogger("PumpController").setLevel(logging.DEBUG)  # Detailed pump communication
logging.getLogger("SerialConnection").setLevel(logging.DEBUG)  # Raw serial data
logging.getLogger("uvicorn").setLevel(logging.INFO)

# Create FastAPI app
app = FastAPI(
    title="Gilbarco SK700-II Pump Controller API",
    description="API for controlling Gilbarco SK700-II fuel dispensers",
    version="1.0.0",
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

# Global pump manager instance
pump_manager = PumpManager()
logger = logging.getLogger("API")

@app.on_event("startup")
async def startup_event():
    """Initialize the pump manager on startup"""
    logger.info("=== Starting Gilbarco SK700-II Pump Controller API ===")
    logger.info(f"API Version: 1.0.0")
    logger.info(f"Startup time: {datetime.now()}")
    logger.info("Swagger UI available at: /docs")
    logger.info("ReDoc available at: /redoc")
    # You can add any initialization code here

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("=== Shutting down Pump Controller API ===")
    pump_manager.shutdown()
    logger.info("API shutdown complete")

@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "message": "Gilbarco SK700-II Pump Controller API",
        "version": "1.0.0",
        "timestamp": datetime.now(),
        "docs": "/docs"
    }

@app.get("/health", tags=["General"])
async def health_check():
    """Health check endpoint"""
    pumps = pump_manager.get_all_pumps()
    connected_pumps = sum(1 for pump in pumps if pump.is_connected)
    
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "total_pumps": len(pumps),
        "connected_pumps": connected_pumps
    }

# Pump Discovery Endpoints
@app.post("/pumps/discover", response_model=PumpDiscoveryResult, tags=["Pump Discovery"])
async def discover_pumps(
    com_ports: Optional[List[str]] = None,
    min_address: int = 1,
    max_address: int = 16,
    timeout: float = 2.0
):
    """
    Discover pumps on COM ports
    
    - **com_ports**: List of COM ports to scan (e.g., ["COM1", "COM2"]). If not provided, all available ports will be scanned
    - **min_address**: Minimum pump address to test (default: 1)
    - **max_address**: Maximum pump address to test (default: 16)
    - **timeout**: Timeout in seconds for each pump test (default: 2.0)
    """
    try:
        logger.info(f"=== API: Pump Discovery Request ===")
        logger.info(f"COM ports: {com_ports or 'All available'}")
        logger.info(f"Address range: {min_address} to {max_address}")
        logger.info(f"Timeout: {timeout}s")
        
        result = pump_manager.discover_pumps(
            com_ports=com_ports,
            address_range=(min_address, max_address),
            timeout=timeout
        )
        
        logger.info(f"=== API: Discovery Complete ===")
        logger.info(f"Total pumps found: {result.total_found}")
        logger.info(f"Scan duration: {result.scan_duration:.2f}s")
        
        return result
    except Exception as e:
        logger.error(f"API: Error discovering pumps: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discover pumps: {str(e)}"
        )

@app.post("/pumps/discover/auto-add", tags=["Pump Discovery"])
async def discover_and_add_pumps(
    com_ports: Optional[List[str]] = None,
    min_address: int = 1,
    max_address: int = 16,
    timeout: float = 2.0
):
    """
    Discover pumps and automatically add them to the system
    """
    try:
        # First discover pumps
        discovery_result = pump_manager.discover_pumps(
            com_ports=com_ports,
            address_range=(min_address, max_address),
            timeout=timeout
        )
        
        # Add discovered pumps
        added_count = pump_manager.auto_add_discovered_pumps(discovery_result)
        
        return {
            "discovery_result": discovery_result,
            "pumps_added": added_count,
            "message": f"Discovered {discovery_result.total_found} pumps, added {added_count} to system"
        }
    except Exception as e:
        logger.error(f"Error in discover and add: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discover and add pumps: {str(e)}"
        )

# Pump Management Endpoints
@app.get("/pumps", response_model=List[PumpInfo], tags=["Pump Management"])
async def get_all_pumps():
    """Get information about all pumps in the system"""
    try:
        pumps = pump_manager.get_all_pumps()
        return pumps
    except Exception as e:
        logger.error(f"Error getting pumps: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pumps: {str(e)}"
        )

@app.get("/pumps/{pump_id}", response_model=PumpInfo, tags=["Pump Management"])
async def get_pump(pump_id: int):
    """Get information about a specific pump"""
    try:
        pump_info = pump_manager.get_pump_info(pump_id)
        if not pump_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pump {pump_id} not found"
            )
        return pump_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pump {pump_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pump: {str(e)}"
        )

@app.post("/pumps", response_model=CommandResponse, tags=["Pump Management"])
async def add_pump(pump_info: PumpInfo):
    """Add a new pump to the system"""
    try:
        success = pump_manager.add_pump(pump_info)
        if success:
            return CommandResponse(
                success=True,
                message=f"Pump {pump_info.pump_id} added successfully",
                data={"pump_id": pump_info.pump_id}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to add pump {pump_info.pump_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding pump: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add pump: {str(e)}"
        )

@app.delete("/pumps/{pump_id}", response_model=CommandResponse, tags=["Pump Management"])
async def remove_pump(pump_id: int):
    """Remove a pump from the system"""
    try:
        success = pump_manager.remove_pump(pump_id)
        if success:
            return CommandResponse(
                success=True,
                message=f"Pump {pump_id} removed successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pump {pump_id} not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing pump {pump_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove pump: {str(e)}"
        )

# Pump Status Endpoints
@app.get("/pumps/status", response_model=List[PumpStatusResponse], tags=["Pump Status"])
async def get_all_pump_statuses():
    """Get status of all pumps"""
    try:
        statuses = pump_manager.get_all_pump_statuses()
        return statuses
    except Exception as e:
        logger.error(f"Error getting pump statuses: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pump statuses: {str(e)}"
        )

@app.get("/pumps/{pump_id}/status", response_model=PumpStatusResponse, tags=["Pump Status"])
async def get_pump_status(pump_id: int):
    """Get status of a specific pump"""
    try:
        logger.info(f"API: Getting status for pump {pump_id}")
        
        status = pump_manager.get_pump_status(pump_id)
        if not status:
            logger.warning(f"API: Pump {pump_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pump {pump_id} not found"
            )
        
        logger.info(f"API: Pump {pump_id} status: {status.status.value}")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Error getting pump {pump_id} status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pump status: {str(e)}"
        )

# Pump Connection Endpoints
@app.post("/pumps/{pump_id}/connect", response_model=CommandResponse, tags=["Pump Connection"])
async def connect_pump(pump_id: int):
    """Connect to a specific pump"""
    try:
        success = pump_manager.connect_pump(pump_id)
        if success:
            return CommandResponse(
                success=True,
                message=f"Connected to pump {pump_id}"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to connect to pump {pump_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting to pump {pump_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect to pump: {str(e)}"
        )

@app.post("/pumps/{pump_id}/disconnect", response_model=CommandResponse, tags=["Pump Connection"])
async def disconnect_pump(pump_id: int):
    """Disconnect from a specific pump"""
    try:
        success = pump_manager.disconnect_pump(pump_id)
        if success:
            return CommandResponse(
                success=True,
                message=f"Disconnected from pump {pump_id}"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pump {pump_id} not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting from pump {pump_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect from pump: {str(e)}"
        )

@app.post("/pumps/connect-all", tags=["Pump Connection"])
async def connect_all_pumps():
    """Connect to all pumps in the system"""
    try:
        results = pump_manager.connect_all_pumps()
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        return {
            "total_pumps": total,
            "successful_connections": successful,
            "failed_connections": total - successful,
            "results": results,
            "message": f"Connected to {successful}/{total} pumps"
        }
    except Exception as e:
        logger.error(f"Error connecting to all pumps: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect to pumps: {str(e)}"
        )

# Pump Control Endpoints
@app.post("/pumps/{pump_id}/authorize", tags=["Pump Control"])
async def authorize_pump(pump_id: str):
    """Authorize a pump for dispensing"""
    try:
        pump_controller = pump_manager.get_pump_controller(pump_id)
        if not pump_controller:
            raise HTTPException(status_code=404, detail="Pump not found")
        
        success = pump_controller.authorize_pump()
        
        if success:
            return {"message": f"Pump {pump_id} authorized successfully"}
        else:
            return {"message": f"Failed to authorize pump {pump_id}", "success": False}
            
    except Exception as e:
        logger.error(f"Error authorizing pump {pump_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/pumps/{pump_id}/stop", tags=["Pump Control"])
async def stop_pump(pump_id: str):
    """Stop a pump"""
    try:
        pump_controller = pump_manager.get_pump_controller(pump_id)
        if not pump_controller:
            raise HTTPException(status_code=404, detail="Pump not found")
        
        success = pump_controller.stop_pump()
        
        if success:
            return {"message": f"Pump {pump_id} stopped successfully"}
        else:
            return {"message": f"Failed to stop pump {pump_id}", "success": False}
            
    except Exception as e:
        logger.error(f"Error stopping pump {pump_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/pumps/all/stop", tags=["Pump Control"])
async def stop_all_pumps():
    """Emergency stop all pumps"""
    try:
        # In a real implementation, this would use the all-stop command
        # For now, stop each pump individually
        results = {}
        
        for pump_id in pump_manager.get_pump_ids():
            pump_controller = pump_manager.get_pump_controller(pump_id)
            if pump_controller:
                success = pump_controller.stop_pump()
                results[pump_id] = success
        
        return {
            "message": "All stop command executed",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error stopping all pumps: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Future extensibility - Generic command endpoint
@app.post("/pumps/{pump_id}/command", response_model=CommandResponse, tags=["Pump Commands"])
async def send_pump_command(pump_id: int, command_request: CommandRequest):
    """
    Send a generic command to a pump (for future extensibility)
    
    This endpoint allows for future commands to be added without changing the API structure.
    """
    try:
        # For now, return a placeholder response
        # Future implementation will handle specific commands
        return CommandResponse(
            success=False,
            message=f"Generic command '{command_request.command}' not implemented yet",
            data={"pump_id": pump_id, "command": command_request.command}
        )
    except Exception as e:
        logger.error(f"Error sending command to pump {pump_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send command: {str(e)}"
        )

# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal Server Error",
            message="An unexpected error occurred",
            details={"exception": str(exc)},
            timestamp=datetime.now()
        ).dict()
    )

if __name__ == "__main__":
    # Run the API server
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True
    )
