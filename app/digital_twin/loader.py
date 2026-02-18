import json
import math
import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ScenarioLoader:
    def __init__(self, scenario_path: str):
        self.scenario_path = scenario_path
        self.data = self._load_scenario()

    def _load_scenario(self) -> Dict[str, Any]:
        try:
            with open(self.scenario_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load scenario {self.scenario_path}: {e}")
            return {}

    def get_weather_at(self, day_index: int, hour: float) -> Dict[str, float]:
        """Get weather conditions (T_ext, nebulosity) for a given time."""
        days = self.data.get("weather", [])
        day_data = days[day_index % len(days)] # Loop if scenario is shorter
        
        # Interpolate Temperature (Sinusoidal between min/max)
        t_min = day_data.get("t_min", 0)
        t_max = day_data.get("t_max", 10)
        
        # Classic day cycle: Min at 4am, Max at 4pm (16h)
        # T(h) = (Tmax+Tmin)/2 - (Tmax-Tmin)/2 * cos(pi * (h - 4) / 12)
        avg = (t_max + t_min) / 2
        amp = (t_max - t_min) / 2
        t_ext = avg - amp * math.cos(math.pi * (hour - 4) / 12)
        
        return {
            "temperature": t_ext,
            "nebulosity": day_data.get("nebulosity", 0.0)
        }

    def get_price_at(self, day_index: int, hour: float) -> Dict[str, Any]:
        """Get electricity price and tariff type (HP/HC) for a given time."""
        prices = self.data.get("prices", {})
        hp_price = prices.get("hp", 0.2516)
        hc_price = prices.get("hc", 0.2068)
        peak_hours = prices.get("peak_hours", [[6, 14], [17, 21]])
        
        # Check if current hour falls within a peak period
        is_peak = False
        for start, end in peak_hours:
            if start <= hour < end:
                is_peak = True
                break
        
        if is_peak:
            return {"price": hp_price, "tariff": "HP"}
        else:
            return {"price": hc_price, "tariff": "HC"}
