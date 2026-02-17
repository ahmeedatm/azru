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
# We need to break the circular dependency or use setter
# Option: Initialize MQTTService, then set mpc_service later
mqtt_service = MQTTService(influx_service)
mpc_service = MPCService(influx_service)

# Dependency Injection for Time Sync
mqtt_service.mpc_service = mpc_service

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
    if result is None:
        return {"status": "skipped", "reason": "Manual Mode Active"}
    
    # Publish result to MQTT
    if "valve_position" in result:
        payload = json.dumps(result)
        topic = "home/bureau/valve/set"
        # Since mqtt_service.client is initialized in mqtt_service, we might need to access it publicly or add a publish method
        # Let's add a quick publish method to MQTTService or access client directly if possible
        # Ideally MQTTService should handle publishing.
        await mqtt_service.client.publish(topic, payload) 
        logger.info(f"Published decision: {topic} -> {payload}")
        
    return result

from pydantic import BaseModel

class ValveControlRequest(BaseModel):
    valve_position: int

class ModeControlRequest(BaseModel):
    auto_mode: bool

@app.post("/control/valve")
async def manual_valve_control(request: ValveControlRequest):
    """Manually set valve position and switch to Manual Mode."""
    # 1. Switch to Manual Mode
    mpc_service.set_auto_mode(False)
    
    # 2. Publish Command
    sim_time = mpc_service.current_time.isoformat()
    payload = json.dumps({
        "valve_position": request.valve_position, 
        "source": "manual",
        "sim_time": sim_time
    })
    topic = "home/bureau/valve/set" # TODO: Dynamic room
    
    if mqtt_service.client:
        await mqtt_service.client.publish(topic, payload)
        logger.info(f"Manual Command: {topic} -> {payload}")
        return {"status": "success", "mode": "manual", "valve_position": request.valve_position}
    else:
        return {"status": "error", "message": "MQTT Client not connected"}

@app.post("/control/mode")
async def set_control_mode(request: ModeControlRequest):
    """Switch between Auto (MPC) and Manual modes."""
    mpc_service.set_auto_mode(request.auto_mode)
    return {"status": "success", "auto_mode": request.auto_mode}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "app": settings.APP_NAME}

@app.get("/")
async def root():
    return {"message": "Welcome to Azru"}
