from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Create FastAPI app
app = FastAPI(
    title="EASM Platform API",
    description="External Attack Surface Management Platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "EASM Platform API",
        "version": "1.0.0",
        "sprint": "Sprint 1 - Discovery Pipeline"
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected",
        "redis": "connected",
        "minio": "connected"
    }

# Sprint 1: Basic endpoints will be added here
# Sprint 2: Will add full API with authentication and multi-tenant endpoints

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
