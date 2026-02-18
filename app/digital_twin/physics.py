import logging
import math
from datetime import datetime
try:
    from app.digital_twin.rc_simulator.building_physics import Zone
    from app.digital_twin.rc_simulator import supply_system
    from app.digital_twin.rc_simulator import emission_system
except ImportError:
    # Safe fallback for local dev without the library installed
    Zone = None
    logging.warning("RC_BuildingSimulator not found. Physics will fail if run.")

from app.config import settings

logger = logging.getLogger(__name__)

class BuildingPhysics:
    def __init__(self):
        if Zone is None:
            raise ImportError("RC_BuildingSimulator library is missing. Install it via requirements.txt")
            
        # Map "heavy/light" to thermal capacitance
        # ISO 13790 defaults (J/m2K):
        # Light: 110,000 / Medium: 165,000 / Heavy: 260,000 / Very Heavy: 370,000
        capacitance_map = {
            "light": 110000,
            "medium": 165000,
            "heavy": 260000,
            "very_heavy": 370000
        }
        c_m_factor = capacitance_map.get(settings.SIM_BUILDING_CLASS, 165000)

        # Initialize the Zone with config parameters
        self.zone = Zone(
            window_area=settings.SIM_WINDOW_AREA,
            walls_area=settings.SIM_WALL_AREA,
            floor_area=settings.AREA,
            room_vol=settings.AREA * 2.5, # Assuming 2.5m height
            total_internal_area=settings.AREA * 6, # Rough approximation
            u_walls=settings.SIM_U_WALLS,
            u_windows=settings.SIM_U_WINDOWS,
            ach_vent=0.5, # Default ventilation
            ach_infl=0.2, # Infiltration
            ventilation_efficiency=0.0,
            thermal_capacitance_per_floor_area=c_m_factor,
            t_set_heating=settings.T_MIN,
            t_set_cooling=settings.T_MAX,
        )
        
    def calculate_solar_gain(self, current_time: datetime, nebulosity: float) -> float:
        """
        Calculate solar power entering the room (W).
        Simple model: Max at noon, zero at night.
        """
        hour = current_time.hour + current_time.minute / 60.0
        
        # Simple solar model: sin wave between 6h and 18h
        if 6 <= hour <= 18:
            # Peak solar irradiance (W/m2) - heavily simplified
            max_irradiance = 800 * (1 - nebulosity)
            # Incidence angle factor (sinusoidal)
            angle_factor = math.sin(math.pi * (hour - 6) / 12)
            
            solar_power_density = max_irradiance * angle_factor
            # 0.7 is a default G-value
            return solar_power_density * self.zone.window_area * 0.7
        return 0.0

    def calculate_next_state(self, t_air_prev: float, t_m_prev: float, t_ext: float, 
                           valve_pos: float, p_sol: float, p_int: float) -> tuple[float, float]:
        """
        Calculate T_air and T_m for the next step using the 5R1C model.
        
        :param valve_pos: Valve position (0-100%)
        :return: (t_air_next, t_m_next)
        """
        # Convert Valve % to Heating Power (Watts)
        # Detailed wrapping: The library expects `energy_demand` to be calculated internally 
        # based on setpoints. BUT we want to force the power based on the MPC/Valve.
        # So we bypass `solve_energy` and call `calc_temperatures_crank_nicolson` directly
        # with our forced energy input.
        
        heating_power = (valve_pos / 100.0) * settings.SIM_HEATER_MAX_POWER
        
        # Total gains
        # Note: The library function signature is:
        # calc_temperatures_crank_nicolson(self, energy_demand, internal_gains, solar_gains, t_out, t_m_prev)
        
        # We treat our Heating Power as the "energy_demand" supplied to the room.
        # Positive value = Heating.
        
        self.zone.calc_temperatures_crank_nicolson(
            energy_demand=heating_power,
            internal_gains=p_int,
            solar_gains=p_sol,
            t_out=t_ext,
            t_m_prev=t_m_prev
        )
        
        # The zone object updates its internal state: zone.t_air and zone.t_m
        return self.zone.t_air, self.zone.t_m
