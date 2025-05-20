import logging
import os
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

from app.api import auth, schools, users, students, teachers, attendance, academics, finance, communication, parents, custom_fields, notifications, onboarding
from app.database import engine, Base
from app.middleware.authentication import auth_middleware
from app.middleware.logging import setup_logging

# Initialize FastAPI app
app = FastAPI(
    title="School ERP API",
    description="API for School ERP system with multi-school support, attendance tracking, academic management, and more",
    version="1.0.0",
    docs_url=None,
)

# Configure CORS
origins = [
    "http://localhost:5000",
    "http://localhost:8000",
    # Add production domains when deployed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Custom exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )

# Create database tables
@app.on_event("startup")
async def startup():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created or verified")

# Include routers
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(schools.router, prefix="/api", tags=["Schools"])
app.include_router(users.router, prefix="/api", tags=["Users"])
app.include_router(students.router, prefix="/api", tags=["Students"])
app.include_router(teachers.router, prefix="/api", tags=["Teachers"])
app.include_router(attendance.router, prefix="/api", tags=["Attendance"])
app.include_router(academics.router, prefix="/api", tags=["Academics"])
app.include_router(finance.router, prefix="/api", tags=["Finance"])
app.include_router(communication.router, prefix="/api", tags=["Communication"])
app.include_router(parents.router, prefix="/api", tags=["Parents"])
app.include_router(custom_fields.router, prefix="/api", tags=["Custom Fields"])
app.include_router(notifications.router, prefix="/api", tags=["Notifications"])
app.include_router(onboarding.router, prefix="/api", tags=["Onboarding"])

# Custom OpenAPI schema for documentation
@app.get("/api/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title="School ERP API Documentation",
        swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    )

@app.get("/api/openapi.json", include_in_schema=False)
async def get_openapi_endpoint():
    return get_openapi(
        title="School ERP API",
        version="1.0.0",
        description="API for School ERP system",
        routes=app.routes,
    )

@app.get("/", tags=["Root"])
async def root():
    return {"message": "Welcome to School ERP API. Visit /api/docs for documentation."}

# Run the server
if __name__ == "__main__":
    import uvicorn
    # Run the server on port 5000 instead of 8000
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=True)
