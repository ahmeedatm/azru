import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
import json
from app.config import settings
from app.services.mqtt_service import MQTTService
from app.services.influx_service import InfluxService
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.mpc_service import MPCService
from pydantic import BaseModel

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Services
influx_service = InfluxService()
mqtt_service = MQTTService()
mpc_service = MPCService()

COMMAND_TOPIC = settings.MQTT_TOPIC_COMMAND.replace('+', 'chambre')

# --- Callbacks for MQTT ---
async def handle_sensor_data(location: str, data: dict, sim_time):
    await influx_service.write_data(
        measurement="sensors",
        tags={"location": location},
        fields=data,
        timestamp=sim_time
    )

async def handle_valve_set(location: str, data: dict):
    await influx_service.write_data(
        measurement="actuators",
        tags={"location": location, "type": "valve"},
        fields=data
    )

async def handle_clock_sync(iso_time: str):
    mpc_service.update_time(iso_time)

# Dependency Injection / Callback binding
mqtt_service.on_sensor_data = handle_sensor_data
mqtt_service.on_valve_set = handle_valve_set
mqtt_service.on_clock_sync = handle_clock_sync

# Scheduler
scheduler = AsyncIOScheduler()

async def run_mpc_job():
    logger.info("Running scheduled MPC job...")
    
    t_init = await influx_service.get_latest_data(measurement="sensors", location="chambre", field="temperature")
    if t_init is None:
        logger.warning("Could not fetch temperature from InfluxDB, using fallback: 20.0 C")
        t_init = 20.0
        
    result = await mpc_service.optimize(t_init)
    if result and "valve_position" in result:
        payload = json.dumps(result)
        if getattr(mqtt_service, 'client', None):
            await mqtt_service.client.publish(COMMAND_TOPIC, payload) 
            logger.info(f"Published decision: {COMMAND_TOPIC} -> {payload}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup/shutdown)."""
    logger.info("Starting Azru...")
    task = asyncio.create_task(mqtt_service.start())
    
    scheduler.add_job(run_mpc_job, 'interval', minutes=15)
    scheduler.start()
    
    yield
    
    task.cancel()
    scheduler.shutdown()
    await influx_service.close()
    logger.info("Services stopped.")

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan
)

class ValveControlRequest(BaseModel):
    valve_position: int

class ModeControlRequest(BaseModel):
    auto_mode: bool

@app.post("/force-optimization")
async def force_optimization():
    """Trigger MPC optimization manually and publish to MQTT."""
    t_init = await influx_service.get_latest_data(measurement="sensors", location="chambre", field="temperature")
    if t_init is None:
        logger.warning("Could not fetch temperature from InfluxDB, using fallback: 20.0 C")
        t_init = 20.0
        
    result = await mpc_service.optimize(t_init)
    if result is None:
        return {"status": "skipped", "reason": "Manual Mode Active"}
    
    if result and "valve_position" in result:
        payload = json.dumps(result)
        if getattr(mqtt_service, 'client', None):
            await mqtt_service.client.publish(COMMAND_TOPIC, payload) 
            logger.info(f"Published decision: {COMMAND_TOPIC} -> {payload}")
        
    return result

@app.post("/control/valve")
async def manual_valve_control(request: ValveControlRequest):
    """Manually set valve position and switch to Manual Mode."""
    mpc_service.set_auto_mode(False)
    
    sim_time = mpc_service.current_time.isoformat()
    payload = json.dumps({
        "valve_position": request.valve_position, 
        "source": "manual",
        "sim_time": sim_time
    })
    
    if getattr(mqtt_service, 'client', None):
        await mqtt_service.client.publish(COMMAND_TOPIC, payload)
        logger.info(f"Manual Command: {COMMAND_TOPIC} -> {payload}")
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
