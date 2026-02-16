import asyncio
import logging
from aiomqtt import Client
from app.config import settings

logger = logging.getLogger(__name__)

class MQTTService:
    def __init__(self):
        self.client = Client(
            hostname=settings.MQTT_BROKER,
            port=settings.MQTT_PORT
        )

    async def start(self):
        """Connect and subscribe to topics."""
        try:
            async with self.client:
                logger.info(f"Connected to MQTT Broker: {settings.MQTT_BROKER}")
                await self.client.subscribe(settings.MQTT_TOPIC)
                logger.info(f"Subscribed to topic: {settings.MQTT_TOPIC}")
                
                async for message in self.client.messages:
                    payload = message.payload.decode()
                    logger.info(f"Received message on {message.topic}: {payload}")
                    # TODO: Process message and save to InfluxDB
        except Exception as e:
            logger.error(f"MQTT Error: {e}")
            # Simple reconnection logic could be added here or relied on orchestration restart
            await asyncio.sleep(5)
