import asyncio
import logging
import json
from aiomqtt import Client
from app.config import settings

logger = logging.getLogger(__name__)

class MQTTService:
    def __init__(self, influx_service):
        self.influx_service = influx_service
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
                    payload_str = message.payload.decode()
                    topic = message.topic.value
                    logger.info(f"Received message on {topic}: {payload_str}")
                    
                    try:
                        data = json.loads(payload_str)
                        # Topic: home/sensors/<location>/metrics
                        parts = topic.split('/')
                        if len(parts) >= 3:
                            location = parts[2]
                            
                            self.influx_service.write_data(
                                measurement="sensors",
                                tags={"location": location},
                                fields=data
                            )
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON Decode Error: {e}")
                        
        except Exception as e:
            logger.error(f"MQTT Error: {e}")
            # Simple reconnection logic could be added here or relied on orchestration restart
            await asyncio.sleep(5)
