import logging
import numpy as np
import pandas as pd
from datetime import datetime
from gekko import GEKKO
from app.config import settings
from app.models.thermal_model import ThermalModel
from app.services.influx_service import InfluxService

logger = logging.getLogger(__name__)

class MPCService:
    def __init__(self, influx_service: InfluxService):
        self.influx_service = influx_service
        self.model = ThermalModel()
        self.horizon = 24 * 4  # 24h with 15min steps = 96 steps
        self.dt = 900  # 15 min
        self.current_time = datetime.now()
        self.is_auto_mode = True

    def set_auto_mode(self, enabled: bool):
        """Enable or disable MPC automatic control."""
        self.is_auto_mode = enabled
        logger.info(f"MPC Auto Mode set to: {self.is_auto_mode}")

    def update_time(self, iso_time: str):
        """Update internal time from simulation clock."""
        try:
            self.current_time = datetime.fromisoformat(iso_time)
            logger.debug(f"MPC Time updated: {self.current_time}")
        except ValueError as e:
            logger.error(f"Failed to parse time {iso_time}: {e}")

    def get_mock_weather_forecast(self, start_time: datetime | None = None):
        """Mock weather forecast (sinusoidal temperature)."""
        if start_time is None:
             start_time = self.current_time
             
        # Create a time range for the next 24h
        t = np.linspace(0, 24, self.horizon)
        # T_ext varies between 5°C (night) and 15°C (day)
        # Shift sin wave based on start_time hour
        start_hour = start_time.hour
        T_ext = 10 + 5 * np.sin(2 * np.pi * (t + start_hour - 8) / 24)
        return T_ext

    def get_mock_electricity_prices(self):
        """Mock electricity prices (Peak/Off-Peak)."""
        # Peak hours: 7h-10h and 18h-22h
        # Off-peak: 0.15 €/kWh, Peak: 0.25 €/kWh
        prices = np.full(self.horizon, 0.15)
        # We assume simulation starts at midnight for simplicity, or we should map to real time
        # For mock, let's just put some peaks
        prices[28:40] = 0.25 # 7h-10h (approx steps)
        prices[72:88] = 0.25 # 18h-22h
        return prices

    def get_last_indoor_temperature(self) -> float:
        """Retrieve last known temperature from InfluxDB."""
        temp = self.influx_service.get_latest_data(
            measurement="sensors",
            location="chambre",
            field="temperature"
        )
        if temp is not None:
             logger.info(f"Using real temperature from InfluxDB: {temp} C")
             return temp
        
        logger.warning("Could not fetch temperature from InfluxDB, using fallback: 20.0 C")
        return 20.0 

    def optimize(self):
        """Run MPC optimization."""
        if not self.is_auto_mode:
            logger.info("MPC is in MANUAL mode. Skipping optimization.")
            return None

        logger.info("Starting MPC Optimization...")
        
        try:
            # 1. Get Initial State
            T_init = self.get_last_indoor_temperature()
            T_ext_forecast = self.get_mock_weather_forecast()
            Prices_forecast = self.get_mock_electricity_prices()
            
            # 2. Setup GEKKO Model
            m = GEKKO(remote=False) # Attempt local solve first
            m.time = np.linspace(0, self.horizon * self.dt, self.horizon)

            # Variables
            # Indoor Temperature
            Ti = m.Var(value=T_init, lb=5, ub=35, name='Ti')
            # Heating Power (Control Variable): 0 to 3000 W
            P_heat = m.MV(value=0, lb=0, ub=3000, name='P_heat')
            P_heat.STATUS = 1  # Allow optimizer to modify
            P_heat.DCOST = 0   # No cost for changing setting

            # Parameters
            Text = m.Param(value=T_ext_forecast, name='Text')
            Price = m.Param(value=Prices_forecast, name='Price')
            
            # Constants
            R = settings.SIM_ROOM_R
            C = settings.SIM_ROOM_C
            Area = settings.AREA
            Tmin = settings.T_MIN
            Tmax = settings.T_MAX
            Rho = settings.RHO

            # Equation of State (Discretized)
            # dT/dt = (Text - Ti)/(R*Area) + P/C
            m.Equation(Ti.dt() == (Text - Ti) / (R * Area) + P_heat / C)

            # Objective Function
            # Minimize Cost + Penalty for discomfort
            # Cost = Price * Power * dt (Joules to kWh conversion needed usually, but here proportionate)
            # Discomfort = Rho * (max(0, Tmin - Ti)**2) -> Soft constraint
            
            # Since Gekko creates a differential equation model, we minimize the integral objective
            # m.Obj(Price * P_heat + Rho * (Ti - Tmin)**2) 
            # Note: Hard constraints or Soft constraints? 
            # Let's use soft constraint for comfort to ensure feasibility
            
            # Slack variable for comfort violation
            violation = m.Var(value=0, lb=0)
            m.Equation(violation >= Tmin - Ti)
            
            m.Obj(Price * P_heat * 1e-4 + Rho * violation**2) # Scale price to balance with comfort

            # Solve
            m.options.IMODE = 6 # Control
            m.options.NODES = 3 # Collocation nodes
            m.solve(disp=False)

            # 3. Extract Result
            optimal_power = P_heat.NEWVAL
            predicted_temp = Ti.value

            logger.info(f"Optimization Success! Next Power: {optimal_power:.2f} W, Next Temp: {predicted_temp[1]:.2f} C")
            
            # 4. Return control action (0 or 100% or logical PWM)
            # For this MVP, let's say if Power > 0, we turn ON (or use the value/3000 as %)
            valve_position = int((optimal_power / 3000) * 100)
            return {"valve_position": valve_position, "planned_power": optimal_power}

        except Exception as e:
            logger.error(f"MPC Optimization Failed: {e}")
            return {"valve_position": 0, "error": str(e)}
