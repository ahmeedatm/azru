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
    async def connect_and_publish(self):
        async with Client(hostname=settings.MQTT_BROKER, port=settings.MQTT_PORT) as client:
            self.client = client
            logger.info(f"Connected to MQTT Broker: {settings.MQTT_BROKER}")
            while self.running:
                await self.publish_sensor_data()
                await asyncio.sleep(5)

    async def publish_sensor_data(self):
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

    def __init__(self):
        self.running = True



    async def start(self):
        await self.connect_and_publish()

async def main():
    simulator = SensorSimulator()
    await simulator.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Simulator stopped.")
    except KeyboardInterrupt:
        logger.info("Simulator stopped.")
