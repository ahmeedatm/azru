import math
from datetime import datetime
from app.config import settings

class BuildingPhysics:
    def __init__(self, R=None, C=None, area=None, window_area=None):
        self.R = R if R is not None else settings.SIM_ROOM_R
        self.C = C if C is not None else settings.SIM_ROOM_C
        self.area = area if area is not None else settings.AREA
        self.window_area = window_area if window_area is not None else settings.SIM_WINDOW_AREA
        self.solar_factor = 0.7  # G-value of windows

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
            return solar_power_density * self.window_area * self.solar_factor
        return 0.0

    def calculate_next_temp(self, T_current: float, T_ext: float, P_heat: float, 
                          P_int: float, P_sol: float, dt_seconds: float) -> float:
        """
        Calculate T(t+1) using Euler discretization of R1C1 data.
        """
        # Heat flows
        loss_gain = (T_ext - T_current) / (self.R * self.area) # W/m2 ?? No, U = 1/R*Area? 
        # Wait, if R is K.m2/W, then U = 1/R (W/m2.K). 
        # Total conductance UA = Area / R
        
        UA = self.area / self.R 
        
        # Total Power (W)
        P_total = (UA * (T_ext - T_current)) + P_heat + P_sol + P_int
        
        # dT = P_total * dt / C
        dT = (P_total * dt_seconds) / self.C
        
        return T_current + dT
