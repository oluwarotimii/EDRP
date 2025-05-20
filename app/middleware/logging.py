import logging
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings

# Configure logging
def setup_logging():
    """Configure application logging."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Create logs directory if it doesn't exist
    if settings.LOG_FILE:
        log_dir = Path(settings.LOG_FILE).parent
        os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.LOG_FILE) if settings.LOG_FILE else logging.NullHandler(),
        ]
    )
    
    # Set specific log levels for noisy libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Create logger for this application
    logger = logging.getLogger("app")
    logger.setLevel(log_level)
    
    # Add more handlers or configuration as needed
    return logger

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging request details."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = logging.getLogger("app.request")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Add request_id to the request state for use in route handlers
        request.state.request_id = request_id
        
        # Extract user information if available
        user_id = None
        if hasattr(request.state, "user") and request.state.user:
            user_id = request.state.user.id
        
        # Log request details
        self.logger.info(
            f"Request started: {request.method} {request.url.path} "
            f"[client: {request.client.host if request.client else 'unknown'}] "
            f"[user_id: {user_id}] [request_id: {request_id}]"
        )
        
        try:
            response = await call_next(request)
            
            # Calculate request duration
            duration = time.time() - start_time
            
            # Log response details
            self.logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"[status: {response.status_code}] [duration: {duration:.3f}s] "
                f"[request_id: {request_id}]"
            )
            
            # Add request_id header to response
            response.headers["X-Request-ID"] = request_id
            
            return response
        
        except Exception as e:
            # Log exception details
            self.logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"[error: {str(e)}] [request_id: {request_id}]",
                exc_info=True
            )
            raise

def add_logging_middleware(app: FastAPI):
    """Add request logging middleware to the FastAPI app."""
    app.add_middleware(RequestLoggingMiddleware)
