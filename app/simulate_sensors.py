import asyncio
import logging
import random
import json
from aiomqtt import Client
from app.config import settings

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Simulator")

class SensorSimulator:
    def __init__(self):
        self.client = Client(
            hostname=settings.MQTT_BROKER,
            port=settings.MQTT_PORT
        )
        self.running = True

    async def publish_data(self):
        """Simulate sending sensor data every 5 seconds."""
        async with self.client:
            logger.info(f"Connected to MQTT Broker: {settings.MQTT_BROKER}")
            while self.running:
                # Simulate Temperature
                temp = round(random.uniform(18.0, 24.0), 2)
                power = round(random.uniform(100.0, 3000.0), 1)
                
                payload = {
                    "temperature": temp,
                    "power_consumption": power,
                    "battery": random.randint(80, 100)
                }
                
                topic = "home/sensors/living_room/metrics"
                await self.client.publish(topic, json.dumps(payload))
                logger.info(f"Simulated: {topic} -> {payload}")
                
                await asyncio.sleep(5)

    async def start(self):
        await self.publish_data()

if __name__ == "__main__":
    simulator = SensorSimulator()
    try:
        asyncio.run(simulator.start())
    except KeyboardInterrupt:
        logger.info("Simulator stopped.")
