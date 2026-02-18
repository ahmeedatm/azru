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
        
        # Initial Temperatures
        self.T_int = self.loader.data.get("initial_temp", settings.SIM_INITIAL_TEMP)
        # Assume Mass Temperature starts equal to Air Temperature
        self.T_m = self.T_int 
        
        self.valve_pos = 0.0 # 0 to 100%
        self.total_cost = 0.0  # Cumulative heating cost (€)
        self.duration = timedelta(days=self.loader.data.get("duration_days", 3))
        self.sim_start = self.current_sim_time
        self.running = True
        
    async def run(self):
        async with Client(hostname=settings.MQTT_BROKER_HOST, port=settings.MQTT_PORT, 
                          username=settings.MQTT_USERNAME, password=settings.MQTT_PASSWORD) as client:
            self.client = client
            logger.info(f"Connected to MQTT ({settings.MQTT_BROKER_HOST}). Speed: {self.speed_factor}x. Physics: ISO 13790")
            
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
                    
                    # Check if simulation duration is reached
                    if self.current_sim_time - self.sim_start >= self.duration:
                        logger.info(f"Simulation terminée après {self.duration.days} jours | Coût total: {self.total_cost:.4f}€")
                        self.running = False
                        break
                    
                    # 2. Get External Conditions
                    hour = self.current_sim_time.hour + self.current_sim_time.minute/60.0
                    total_days = (self.current_sim_time - datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)).days
                    
                    weather = self.loader.get_weather_at(total_days, hour)
                    T_ext = weather['temperature']
                    nebulosity = weather['nebulosity']
                    
                    # 2b. Get Electricity Tariff
                    pricing = self.loader.get_price_at(total_days, hour)
                    elec_price = pricing['price']   # €/kWh
                    tariff_type = pricing['tariff']  # HP or HC
                    
                    # 3. Calculate Powers (for display/logging, logic is inside physics now)
                    # Heating Power (Watts) - purely for logging, physics recalculates this
                    P_heat_display = (self.valve_pos / 100.0) * settings.SIM_HEATER_MAX_POWER
                    
                    # Solar - purely for logging
                    P_sol = self.physics.calculate_solar_gain(self.current_sim_time, nebulosity)
                    
                    # Internal (Simplified: 0W for now)
                    P_int = 0.0
                    
                    # 4. Physics Step (ISO 13790)
                    # Pass previous states and current forcing factors
                    self.T_int, self.T_m = self.physics.calculate_next_state(
                        t_air_prev=self.T_int,
                        t_m_prev=self.T_m,
                        t_ext=T_ext,
                        valve_pos=self.valve_pos,
                        p_sol=P_sol,
                        p_int=P_int
                    )
                    
                    # 4b. Simple Thermostat Control
                    # Hysteresis: heat ON below T_MIN, OFF above T_MIN + 1°C
                    if self.T_int < settings.T_MIN:
                        self.valve_pos = 100.0
                    elif self.T_int > settings.T_MIN + 1.0:
                        self.valve_pos = 0.0
                    
                    # 5. Calculate Heating Cost
                    # cost = Power(W) × time(h) × price(€/kWh) / 1000(W→kW)
                    cost_step = P_heat_display * (dt_sim / 3600.0) * elec_price / 1000.0
                    self.total_cost += cost_step
                    
                    # 6. Publish State
                    await self.publish_state(T_ext, P_heat_display, P_sol, elec_price, cost_step, tariff_type)
                    
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

    async def publish_state(self, T_ext: float, P_heat: float, P_sol: float,
                           elec_price: float, cost_step: float, tariff_type: str):
        # 1. Clock Sync
        await self.client.publish(settings.MQTT_TOPIC_CLOCK, self.current_sim_time.isoformat())
        
        # 2. Metrics
        # Add noise to temperature reading
        noise = random.gauss(0, settings.SIM_SENSOR_NOISE_STD)
        T_measured = self.T_int + noise
        
        payload = {
            "temperature": round(T_measured, 2),
            "mass_temperature": round(self.T_m, 2),
            "external_temperature": round(T_ext, 2),
            "power_consumption": round(P_heat, 2),
            "solar_power": round(P_sol, 2),
            "valve_position": self.valve_pos,
            "electricity_price": round(elec_price, 4),
            "heating_cost_step": round(cost_step, 6),
            "heating_cost_cumulative": round(self.total_cost, 4),
            "sim_time": self.current_sim_time.isoformat()
        }
        await self.client.publish(settings.MQTT_TOPIC_METRICS, json.dumps(payload))
        logger.info(f"Sim {self.current_sim_time.strftime('%H:%M')} | T={self.T_int:.1f} | Heat={P_heat:.0f}W | {tariff_type} {elec_price:.4f}€ | Total={self.total_cost:.4f}€")

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
