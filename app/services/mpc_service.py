import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import httpx
import asyncio
from gekko import GEKKO
from app.config import settings
from app.models.thermal_model import ThermalModel

logger = logging.getLogger(__name__)

class MPCService:
    def __init__(self):
        self.model = ThermalModel()
        self.dt = settings.SIM_TIME_STEP  # Rendu dynamique via config.py (ex: 3600s = 1h)
        self.horizon = int(24 * 3600 / self.dt)  # Horizon prédictif de 24h
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

    def get_mock_weather_forecast(self, start_time: Optional[datetime] = None):
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

    async def get_tempo_electricity_prices(self, start_time: Optional[datetime] = None):
        """
        Récupère les prix de l'électricité basés sur le modèle EDF Tempo.
        Utilise l'API publique (api-couleur-tempo.fr).
        """
        if start_time is None:
             start_time = self.current_time

        # Tarifs EDF Tempo 2024-2025 (environ, en €/kWh)
        # HP: 6h-22h, HC: 22h-6h
        TARIFS = {
            "Bleu": {"HC": 0.1296, "HP": 0.1609},
            "Blanc": {"HC": 0.1486, "HP": 0.1894},
            "Rouge": {"HC": 0.1568, "HP": 0.7562},
            "Inconnu": {"HC": 0.15, "HP": 0.25} # Fallback
        }

        # 1. Récupération des couleurs du jour et du lendemain
        couleur_aujourdhui = "Inconnu"
        couleur_demain = "Inconnu"
        
        try:
            # API non officielle très fiable, mais appel non-bloquant
            async with httpx.AsyncClient() as client:
                res_today = await client.get("https://www.api-couleur-tempo.fr/api/jourTempo/today", timeout=5.0)
                if res_today.status_code == 200:
                    couleur_aujourdhui = res_today.json().get("libCouleur", "Inconnu")
                    
                res_tomorrow = await client.get("https://www.api-couleur-tempo.fr/api/jourTempo/tomorrow", timeout=5.0)
                if res_tomorrow.status_code == 200:
                    couleur_demain = res_tomorrow.json().get("libCouleur", "Inconnu")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des couleurs Tempo: {e}")

        logger.info(f"Couleurs Tempo - Aujourd'hui: {couleur_aujourdhui}, Demain: {couleur_demain}")

        # 2. Construction du vecteur de prix sur l'horizon
        prices = np.zeros(self.horizon)
        
        current_step_time = start_time
        for i in range(self.horizon):
            # Déterminer si on est sur aujourd'hui ou demain (ou après)
            # Pour simplifier sur 24h, on regarde juste la date
            if current_step_time.date() == start_time.date():
                couleur_jour = couleur_aujourdhui
            else:
                couleur_jour = couleur_demain

            # Les Heures Pleines Tempo sont de 6h à 22h
            is_hp = 6 <= current_step_time.hour < 22
            
            # Récupération du tarif applicable
            tarif_jour = TARIFS.get(couleur_jour, TARIFS["Inconnu"])
            prices[i] = tarif_jour["HP"] if is_hp else tarif_jour["HC"]

            # Avancer d'un pas de temps (dt est en secondes)
            current_step_time += timedelta(seconds=self.dt)
            
        return prices

    async def optimize(self, T_init: float):
        """Run MPC optimization asynchronously based on an initial temperature."""
        if not self.is_auto_mode:
            logger.info("MPC is in MANUAL mode. Skipping optimization.")
            return None

        logger.info(f"Starting MPC Optimization from T_init={T_init:.2f}C...")
        
        try:
            # 1. Forecast state
            T_ext_forecast = self.get_mock_weather_forecast()
            Prices_forecast = await self.get_tempo_electricity_prices()
            
            # 2. Setup GEKKO Model
            m = GEKKO(remote=False) # Attempt local solve first
            m.time = np.linspace(0, self.horizon * self.dt, self.horizon)

            # Variables
            # Indoor Temperature (Large bounds to prevent infeasibility during transient high temps)
            Ti = m.Var(value=T_init, lb=-20, ub=60, name='Ti')
            # Heating Power (Control Variable)
            P_heat = m.MV(value=0, lb=0, ub=settings.SIM_HEATER_MAX_POWER, name='P_heat')
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
            # Thermodynamique: dT/dt = (Text - Ti)*Area/(R*C) + P/C
            m.Equation(Ti.dt() == (Text - Ti) * Area / (R * C) + P_heat / C)

            # Objective Function
            # Minimize Cost + Penalty for discomfort
            # Discomfort = Rho * (max(0, Tmin - Ti)**2) + Rho * (max(0, Ti - Tmax)**2)
            
            # Variables de relaxation (slack) pour confort violation min et max
            violation_min = m.Var(value=0, lb=0)
            violation_max = m.Var(value=0, lb=0)
            
            m.Equation(violation_min >= Tmin - Ti)
            m.Equation(violation_max >= Ti - Tmax)
            
            # Pénalité asymétrique: chauffer pour rien coûte cher, donc surchauffe très réprimée
            penalty_weight = Rho * 10 
            
            m.Obj(Price * P_heat * 1e-4 + Rho * violation_min**2 + penalty_weight * violation_max**2)

            # Solve
            m.options.IMODE = 6 # Control
            m.options.NODES = 3 # Collocation nodes
            await asyncio.to_thread(m.solve, disp=False)

            # 3. Extract Result
            optimal_power = P_heat.NEWVAL
            predicted_temp = Ti.value

            logger.info(f"Optimization Success! Next Power: {optimal_power:.2f} W, Next Temp: {predicted_temp[1]:.2f} C")
            
            # 4. Return control action (0 or 100% or logical PWM)
            # For this MVP, let's say if Power > 0, we turn ON (or use the value/MAX as %)
            valve_position = int((optimal_power / settings.SIM_HEATER_MAX_POWER) * 100)
            return {"valve_position": valve_position, "planned_power": optimal_power}

        except Exception as e:
            logger.error(f"MPC Optimization Failed: {e}")
            # En cas d'échec, stratégie de sécurité : on coupe le chauffage
            return {"valve_position": 0, "planned_power": 0.0, "error": str(e)}
