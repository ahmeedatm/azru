import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.services.mqtt_service import MQTTService
from app.services.influx_service import InfluxService

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Services
influx_service = InfluxService()
mqtt_service = MQTTService(influx_service)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup/shutdown)."""
    # Start MQTT task in background
    logger.info("Starting Azru...")
    task = asyncio.create_task(mqtt_service.start())
    yield
    # Cleanup
    task.cancel()
    influx_service.close()
    logger.info("Services stopped.")

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "app": settings.APP_NAME}

@app.get("/")
async def root():
    return {"message": "Welcome to Azru"}
