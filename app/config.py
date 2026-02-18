from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Azru"
    
    # MQTT Config
    # MQTT Config
    MQTT_BROKER: str = "mosquitto" # Keeping for backward compat or use MQTT_BROKER_HOST
    MQTT_BROKER_HOST: str = "mosquitto"
    MQTT_PORT: int = 1883
    MQTT_USERNAME: str = "admin"
    MQTT_PASSWORD: str = "ton_mot_de_passe_secret"
    
    MQTT_TOPIC: str = "home/#"
    MQTT_TOPIC_COMMAND: str = "home/+/valve/set"
    MQTT_TOPIC_METRICS: str = "home/sensors/chambre/metrics"
    MQTT_TOPIC_CLOCK: str = "home/sys/clock"
    
    # InfluxDB Config
    INFLUXDB_URL: str
    INFLUXDB_TOKEN: str
    INFLUXDB_ORG: str
    INFLUXDB_BUCKET: str

    # Simulation Config
    SIM_SPEED_FACTOR: int = 120
    SIM_TIME_STEP: int = 60
    SIM_SCENARIO_FILE: str = "app/digital_twin/scenarios/scenario_neige.json"
    SIM_START_DATE: str = "2026-02-17T00:00:00" # Fixed start date for reproducibility
    SIM_INITIAL_TEMP: float = 19.0
    SIM_SENSOR_NOISE_STD: float = 0.1

    # Physics Model Config (ISO 13790 / 5R1C)
    SIM_BUILDING_CLASS: str = "medium" # light, medium, heavy, very_heavy
    SIM_WINDOW_AREA: float = 4.0 # m2
    SIM_WALL_AREA: float = 20.0 # m2 (Approximation based on Area)
    SIM_U_WALLS: float = 0.2
    SIM_U_WINDOWS: float = 1.1

    # SIM_HEATER_MAX_POWER is still used in simulator.py for display calculation so keep it.
    SIM_HEATER_MAX_POWER: float = 3000.0 # Watts

    # MPC / Legacy Model Config
    # The MPC still uses a simplified R1C1 model for optimization.
    # We provide these constants to avoid breaking the MPCService.
    SIM_ROOM_R: float = 2.0  # R value (K.m2/W)
    SIM_ROOM_C: float = 6000000.0  # C value (J/K)

    # Legacy/Internal Config (can rely on above or defaults)
    AREA: float = 20.0  # Surface area (m2)
    T_MIN: float = 19.0
    T_MAX: float = 28.0
    RHO: float = 10.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
