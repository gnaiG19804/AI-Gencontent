"""
AI Content Generator API

Main application entry point with router registration.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from routers import upload, generate, pricing, shopify, price_sync
from core.logging import router as logging_router

app = FastAPI(
    title="AI Content Generator",
    description="Generate AI content and push to Shopify",
    version="2.0.0"
)

# Initialize Database (Tortoise ORM)
from core.database import init_db
init_db(app)

# CORS Configuration
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(logging_router)           # /logs
app.include_router(upload.router)            # /upload, /data
app.include_router(generate.router)          # /generate, /build-product
app.include_router(pricing.router)           # /calculate-price
app.include_router(shopify.router)           # /push-to-shopify
app.include_router(price_sync.router)        # /price-sync (N8N)


@app.get("/api/content")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Connected!"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)