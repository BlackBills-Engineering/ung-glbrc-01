"""
Startup script for the Gilbarco SK700-II Control System
"""

import sys
import logging
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import Config


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format=Config.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs.log')
        ]
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Gilbarco SK700-II Control System"
    )
    parser.add_argument(
        "--host", 
        default=Config.API_HOST, 
        help="API server host"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=Config.API_PORT, 
        help="API server port"
    )
    parser.add_argument(
        "--reload", 
        action="store_true", 
        default=Config.API_RELOAD,
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--log-level", 
        default=Config.LOG_LEVEL,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Update config with command line arguments
    Config.API_HOST = args.host
    Config.API_PORT = args.port
    Config.API_RELOAD = args.reload
    Config.LOG_LEVEL = args.log_level
    
    # Setup logging
    setup_logging()
    
    logger = logging.getLogger("GilbarcoStartup")
    logger.info("Starting Gilbarco SK700-II Control System")
    logger.info(f"Configuration: {Config.get_all_settings()}")
    
    try:
        import uvicorn
        from main import app
        
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level.lower()
        )
        
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error("Please install dependencies: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
