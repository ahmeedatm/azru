from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Azru"
    
    # MQTT Config
    MQTT_BROKER: str
    MQTT_PORT: int = 1883
    MQTT_TOPIC: str = "home/#"
    
    # InfluxDB Config
    INFLUXDB_URL: str
    INFLUXDB_TOKEN: str
    INFLUXDB_ORG: str
    INFLUXDB_BUCKET: str
    # MPC & Thermal Model Config
    R: float = 0.5  # Thermal Resistance (K.m2/W)
    C: float = 1000000.0  # Thermal Capacitance (J/K)
    AREA: float = 20.0  # Surface area (m2)
    T_MIN: float = 19.0  # Minimum required temperature
    T_MAX: float = 28.0 # Maximum allowed temperature
    RHO: float = 10.0  # Penalty weight for comfort violation

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
