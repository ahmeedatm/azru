import logging
import json
import asyncio
from datetime import datetime
from typing import Callable, Awaitable, Any, Optional
from aiomqtt import Client
from aiomqtt.exceptions import MqttError
from app.config import settings

logger = logging.getLogger(__name__)

class MQTTService:
    def __init__(self):
        self.client = Client(
            hostname=settings.MQTT_BROKER_HOST, # Update par rapport settings pour docker/local
            port=settings.MQTT_PORT,
            username=settings.MQTT_USERNAME,
            password=settings.MQTT_PASSWORD
        )
        self.on_sensor_data: Optional[Callable[[str, dict, Any], Awaitable[None]]] = None
        self.on_valve_set: Optional[Callable[[str, dict], Awaitable[None]]] = None
        self.on_clock_sync: Optional[Callable[[str], Awaitable[None]]] = None

    async def start(self):
        """Connect and subscribe to topics with infinite reconnection on network loss."""
        reconnect_interval = 5
        while True:
            try:
                async with self.client:
                    logger.info(f"Connected to MQTT Broker: {settings.MQTT_BROKER_HOST}")
                    await self.client.subscribe(settings.MQTT_TOPIC)
                    logger.info(f"Subscribed to topic: {settings.MQTT_TOPIC}")
                    
                    async for message in self.client.messages:
                        payload_str = message.payload.decode()
                        topic = message.topic.value
                        logger.info(f"Received message on {topic}: {payload_str}")
                        
                        try:
                            data = json.loads(payload_str)
                            parts = topic.split('/')
                            if len(parts) >= 3:
                                if "sensors" in parts:
                                    location = parts[2]
                                    sim_time = None
                                    if "sim_time" in data:
                                        try:
                                            sim_time = datetime.fromisoformat(data["sim_time"].replace('Z', '+00:00'))
                                        except ValueError:
                                            pass
                                    
                                    if self.on_sensor_data:
                                        await self.on_sensor_data(location, data, sim_time)
                                        
                                elif "valve" in parts and "set" in parts:
                                    location = parts[1]
                                    if self.on_valve_set:
                                        await self.on_valve_set(location, data)
                                        
                            elif "sys" in parts and "clock" in parts:
                                if self.on_clock_sync:
                                    await self.on_clock_sync(payload_str)
                                    
                        except json.JSONDecodeError as e:
                            if "clock" in topic:
                                if self.on_clock_sync:
                                    await self.on_clock_sync(payload_str)
                            else:
                                logger.error(f"JSON Decode Error: {e}")
                            
            except MqttError as error:
                logger.error(f'MQTT Error "{error}". Reconnecting in {reconnect_interval} seconds.')
            except asyncio.CancelledError:
                logger.info("MQTT Listener task cancelled.")
                break
            except Exception as e:
                logger.error(f"Unexpected MQTT Exception: {e}")
            
            await asyncio.sleep(reconnect_interval)
