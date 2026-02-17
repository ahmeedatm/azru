from app.config import settings

class ThermalModel:
    """
    Simple R1C1 Thermal Model.
    Equation: T(t+1) = T(t) + (dt / C) * ((T_ext - T(t)) / R + P_heat)
    """
    def __init__(self):
        self.R = settings.R
        self.C = settings.C
        self.area = settings.AREA

    def predict_next_temperature(self, T_in: float, T_ext: float, Power: float, dt: float = 900) -> float:
        """
        Predict temperature at t + dt.
        dt: time step in seconds (default 15 min = 900s)
        Power: Heating power in Watts
        """
        dT_dt = ((T_ext - T_in) / (self.R * self.area)) + (Power / self.C)
        return T_in + dT_dt * dt
