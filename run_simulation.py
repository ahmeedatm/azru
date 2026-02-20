import asyncio
import logging
import argparse
from datetime import datetime, timedelta
import os
import random
import sys

# Hack pour développement local hors-docker
if not os.environ.get("INFLUX_HOST"):
    os.environ["INFLUX_HOST"] = "localhost"
if not os.environ.get("INFLUXDB_URL"):
    os.environ["INFLUXDB_URL"] = "http://localhost:8086"
if not os.environ.get("MQTT_BROKER"):
    os.environ["MQTT_BROKER"] = "localhost"

from app.config import settings
from app.digital_twin.physics import BuildingPhysics
from app.digital_twin.loader import ScenarioLoader
from app.services.influx_service import InfluxService
from app.services.mpc_service import MPCService
from app.services.manual_controller import ManualController

# Mute noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BatchSimulator")


async def run_batch_simulation(start_date_str: str, end_date_str: str, mode: str, reset_db: bool):
    """Exécute une simulation thermique accélérée sans attendre le temps réel."""
    logger.info("==================================================")
    logger.info(f"Démarrage Simulation Batch: {start_date_str} to {end_date_str}")
    logger.info(f"Mode de contrôle: {mode.upper()}")
    logger.info("==================================================")

    start_date = datetime.fromisoformat(start_date_str)
    end_date = datetime.fromisoformat(end_date_str)
    
    if start_date >= end_date:
        logger.error("La date de fin doit être postérieure à la date de début.")
        return

    # Services Init
    influx_service = InfluxService()
    
    if reset_db:
        logger.warning("Vidage de la base de données InfluxDB...")
        influx_service.clear_database()
    
    # Init Physics & Loader
    loader = ScenarioLoader(settings.SIM_SCENARIO_FILE)
    physics = BuildingPhysics()
    
    # Controllers
    if mode == "mpc":
        controller = MPCService()
    else:
        controller = ManualController(target_temp=20.0, trigger_delta=0.5)

    # Initial State
    current_time = start_date
    T_int = loader.data.get("initial_temp", settings.SIM_INITIAL_TEMP)
    T_m = T_int
    valve_pos = 0.0
    total_cost = 0.0
    dt_sim = settings.SIM_TIME_STEP # 900s (15 min) par defaut pour coller avec MPC, mais on utilise les settings
    
    step_count = 0
    total_steps = int((end_date - start_date).total_seconds() / dt_sim)
    
    logger.info(f"Paramètres: dt={dt_sim}s, total_steps={total_steps}, T_init={T_int}°C")

    # ----- MAIN LOOP -----
    while current_time < end_date:
        # 1. Obtenir les Conditions Extérieures
        hour = current_time.hour + current_time.minute / 60.0
        # Utiliser un jour générique du scenario (on boucle si la simu dépasse les jours scénarisés)
        sim_day = (current_time - start_date).days % max(1, loader.data.get("duration_days", 3))
        
        weather = loader.get_weather_at(sim_day, hour)
        T_ext = weather['temperature']
        nebulosity = weather['nebulosity']
        
        # 2. Obtenir les Prix
        pricing = loader.get_price_at(sim_day, hour)
        elec_price = pricing['price']
        tariff_type = pricing['tariff']

        # 3. Mettre à Jour Contrôleur & Demander Action
        if mode == "mpc":
            controller.update_time(current_time.isoformat())
            # Le MPC tourne toutes les X minutes (15 min en général). 
            # Dans ce MVP, on l'appelle à chaque pas de temps pour recalculer.
            action = await controller.optimize(T_int)
            if action and "valve_position" in action:
                valve_pos = action["valve_position"]
        else:
            action = await controller.optimize(T_int)
            valve_pos = action["valve_position"]

        # 4. Calculer la Physique
        P_heat_requested = (float(valve_pos) / 100.0) * float(settings.SIM_HEATER_MAX_POWER)
        P_sol = physics.calculate_solar_gain(current_time, nebulosity)
        P_int = 0.0

        T_int_next, T_m_next = physics.calculate_next_state(
            t_air_prev=T_int,
            t_m_prev=T_m,
            t_ext=T_ext,
            valve_pos=valve_pos,
            p_sol=P_sol,
            p_int=P_int
        )
        
        # 5. Mettre à jour l'état et calculer le coût
        T_int = T_int_next
        T_m = T_m_next
        current_time += timedelta(seconds=dt_sim)
        
        cost_step = P_heat_requested * (dt_sim / 3600.0) * elec_price / 1000.0
        total_cost += cost_step

        # 6. Écriture InfluxDB (Accélérée, batch)
        # On écrit directement sans passer par MQTT
        if True: # On log tout, mais on évite de spammer la console
            if step_count % int(24 * 3600 / dt_sim) == 0: # Tous les jours
                logger.info(f"Progression: {current_time} | T_int={T_int:.2f}°C | Valve={valve_pos}% | Cost={total_cost:.2f}€")

        # Sauvegarde InfluxDB pour Grafana
        noise = random.gauss(0, settings.SIM_SENSOR_NOISE_STD)
        T_measured = T_int + noise
        
        await influx_service.write_data(
            measurement="sensors",
            tags={"location": "chambre"},
            fields={
                "temperature": float(T_measured),
                "mass_temperature": float(T_m),
                "external_temperature": float(T_ext),
                "power_consumption": float(P_heat_requested),
                "solar_power": float(P_sol),
                "valve_position": float(valve_pos),
                "electricity_price": float(elec_price),
                "heating_cost_step": float(cost_step),
                "heating_cost_cumulative": float(total_cost)
            },
            timestamp=current_time
        )
        
        step_count += 1

    # End
    logger.info("==================================================")
    logger.info(f"Simulation Terminée ! Mode={mode}. Coût Total: {total_cost:.2f}€")
    logger.info("==================================================")
    await influx_service.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Digital Twin Offline Batch Simulation")
    parser.add_argument("--start", type=str, required=False, help="ISO start date (e.g., 2026-02-01T00:00:00)")
    parser.add_argument("--end", type=str, required=False, help="ISO end date (e.g., 2026-02-05T00:00:00)")
    parser.add_argument("--mode", type=str, choices=["mpc", "manual"], default="manual", help="Control strategy")
    parser.add_argument("--reset", action="store_true", help="Clear InfluxDB before starting (or alone)")
    
    args = parser.parse_args()
    
    if args.reset and (not args.start or not args.end):
        logger.info("Exécution du reset InfluxDB seul...")
        from app.services.influx_service import InfluxService
        service = InfluxService()
        service.clear_database()
        asyncio.run(service.close())
        sys.exit(0)
        
    if not args.start or not args.end:
        parser.error("--start and --end are required when running a simulation.")
    
    asyncio.run(run_batch_simulation(
        start_date_str=args.start,
        end_date_str=args.end,
        mode=args.mode,
        reset_db=args.reset
    ))
