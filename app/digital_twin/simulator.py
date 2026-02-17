import asyncio
import logging
import json
import time
import random
from datetime import datetime, timedelta
from aiomqtt import Client
from app.config import settings
from app.digital_twin.physics import BuildingPhysics
from app.digital_twin.loader import ScenarioLoader

logger = logging.getLogger("Simulator")
logging.basicConfig(level=logging.INFO)

class Simulator:
    def __init__(self, scenario_file=None, speed_factor=None):
        self.scenario_file = scenario_file if scenario_file else settings.SIM_SCENARIO_FILE
        self.speed_factor = speed_factor if speed_factor else settings.SIM_SPEED_FACTOR
        
        self.loader = ScenarioLoader(self.scenario_file)
        self.physics = BuildingPhysics() # Will use settings defaults
        
        # State
        # Start at current wall-clock time. 
        # Since speed > 1, simulation will drift into the future.
        self.current_sim_time = datetime.now().replace(microsecond=0)
        self.T_int = self.loader.data.get("initial_temp", settings.SIM_INITIAL_TEMP)
        self.valve_pos = 0.0 # 0 to 100%
        self.running = True
        
    async def run(self):
        async with Client(hostname=settings.MQTT_BROKER_HOST, port=settings.MQTT_PORT, 
                          username=settings.MQTT_USERNAME, password=settings.MQTT_PASSWORD) as client:
            self.client = client
            logger.info(f"Connected to MQTT ({settings.MQTT_BROKER_HOST}). Speed: {self.speed_factor}x")
            
            # Subscribe to valve control
            # Topic e.g. "home/+/valve/set"
            await client.subscribe(settings.MQTT_TOPIC_COMMAND)
            
            # Start listener task in background
            listener_task = asyncio.create_task(self.listen_for_commands())

            # Main Loop
            try:
                while self.running:
                    loop_start = time.time()
                    
                    # 1. Advance Time
                    dt_sim = settings.SIM_TIME_STEP # e.g. 60 seconds
                    self.current_sim_time += timedelta(seconds=dt_sim)
                    
                    # 2. Get External Conditions
                    hour = self.current_sim_time.hour + self.current_sim_time.minute/60.0
                    total_days = (self.current_sim_time - datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)).days
                    
                    weather = self.loader.get_weather_at(total_days, hour)
                    T_ext = weather['temperature']
                    nebulosity = weather['nebulosity']
                    
                    # 3. Calculate Powers
                    # Heating
                    P_heat = (self.valve_pos / 100.0) * settings.SIM_HEATER_MAX_POWER
                    
                    # Solar
                    P_sol = self.physics.calculate_solar_gain(self.current_sim_time, nebulosity)
                    
                    # Internal (Simplified: 200W if occupied)
                    P_int = 0.0 # TODO: Schedule logic
                    
                    # 4. Physics Step
                    self.T_int = self.physics.calculate_next_temp(
                        self.T_int, T_ext, P_heat, P_int, P_sol, dt_sim
                    )
                    
                    # 5. Publish State
                    await self.publish_state(T_ext, P_heat, P_sol)
                    
                    # 6. Wait (Real Time)
                    # We want dt_sim sim seconds = dt_sim / speed_factor real seconds
                    target_wait = float(dt_sim) / self.speed_factor
                    elapsed = time.time() - loop_start
                    parking = target_wait - elapsed
                    
                    if parking > 0:
                        await asyncio.sleep(parking)
            except asyncio.CancelledError:
                logger.info("Simulation loop cancelled")
            finally:
                listener_task.cancel()

    async def publish_state(self, T_ext: float, P_heat: float, P_sol: float):
        # 1. Clock Sync
        await self.client.publish(settings.MQTT_TOPIC_CLOCK, self.current_sim_time.isoformat())
        
        # 2. Metrics
        # Add noise to temperature reading
        noise = random.gauss(0, settings.SIM_SENSOR_NOISE_STD)
        T_measured = self.T_int + noise
        
        payload = {
            "temperature": round(T_measured, 2),
            "external_temperature": round(T_ext, 2),
            "power_consumption": round(P_heat, 2),
            "solar_power": round(P_sol, 2),
            "valve_position": self.valve_pos,
            "sim_time": self.current_sim_time.isoformat()
        }
        await self.client.publish(settings.MQTT_TOPIC_METRICS, json.dumps(payload))
        logger.info(f"Sim {self.current_sim_time.strftime('%H:%M')} | T_int={self.T_int:.1f} | T_ext={T_ext:.1f} | Heat={P_heat:.0f}")

    async def listen_for_commands(self):
        async for message in self.client.messages:
            try:
                payload = json.loads(message.payload.decode())
                if "valve_position" in payload:
                    self.valve_pos = float(payload["valve_position"])
                    logger.info(f"Valve updated: {self.valve_pos}%")
            except Exception as e:
                logger.error(f"MQTT Error: {e}")

if __name__ == "__main__":
    sim = Simulator()
    asyncio.run(sim.run())
