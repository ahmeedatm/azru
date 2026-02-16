from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Azru"
    
    # MQTT Config
    MQTT_BROKER: str
    MQTT_PORT: int = 1883
    MQTT_TOPIC: str = "home/sensors/#"
    
    # InfluxDB Config
    INFLUXDB_URL: str
    INFLUXDB_TOKEN: str
    INFLUXDB_ORG: str
    INFLUXDB_BUCKET: str

    class Config:
        env_file = ".env"

settings = Settings()
