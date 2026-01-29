"""
FastAPI application main file
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import health, posts, articles, comments, workflows

# Initialize FastAPI app
app = FastAPI(
    title="TrustStackSocial API",
    description="REST API for TrustStack Social Media Automation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(posts.router, prefix="/api/v1")
app.include_router(articles.router, prefix="/api/v1")
app.include_router(comments.router, prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "TrustStackSocial API",
        "version": "1.0.0",
        "docs": "/docs"
    }
