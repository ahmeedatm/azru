import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
import json
from app.config import settings
from app.services.mqtt_service import MQTTService
from app.services.influx_service import InfluxService

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.mpc_service import MPCService

# Initialize Services
influx_service = InfluxService()
mqtt_service = MQTTService(influx_service)
mpc_service = MPCService(influx_service)

# Scheduler
scheduler = AsyncIOScheduler()

async def run_mpc_job():
    logger.info("Running scheduled MPC job...")
    result = mpc_service.optimize()
    # Publish result to MQTT
    if "valve_position" in result:
        payload = json.dumps(result)
        topic = "home/bureau/valve/set"
        # Since mqtt_service.client is initialized in mqtt_service, we might need to access it publicly or add a publish method
        # Let's add a quick publish method to MQTTService or access client directly if possible
        # Ideally MQTTService should handle publishing.
        await mqtt_service.client.publish(topic, payload) 
        logger.info(f"Published decision: {topic} -> {payload}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup/shutdown)."""
    # Start MQTT task in background
    logger.info("Starting Azru...")
    task = asyncio.create_task(mqtt_service.start())
    
    # Start Scheduler
    scheduler.add_job(run_mpc_job, 'interval', minutes=15)
    scheduler.start()
    
    yield
    # Cleanup
    task.cancel()
    scheduler.shutdown()
    influx_service.close()
    logger.info("Services stopped.")

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan
)

@app.post("/force-optimization")
async def force_optimization():
    """Trigger MPC optimization manually and publish to MQTT."""
    result = mpc_service.optimize()
    
    # Publish result to MQTT
    if "valve_position" in result:
        payload = json.dumps(result)
        topic = "home/bureau/valve/set"
        await mqtt_service.client.publish(topic, payload) 
        logger.info(f"Published decision: {topic} -> {payload}")
        
    return result

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "app": settings.APP_NAME}

@app.get("/")
async def root():
    return {"message": "Welcome to Azru"}
