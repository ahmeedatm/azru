import logging
import json
import asyncio
from datetime import datetime
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
                        # Topic: home/<location>/valve/set
                        parts = topic.split('/')
                        if len(parts) >= 3:
                            if "sensors" in parts:
                                location = parts[2]
                                
                                # Use sim_time from payload for InfluxDB timestamp (Sync with Simulation)
                                sim_time = None
                                if "sim_time" in data:
                                    try:
                                        sim_time = datetime.fromisoformat(data["sim_time"].replace('Z', '+00:00'))
                                    except ValueError:
                                        pass

                                self.influx_service.write_data(
                                    measurement="sensors",
                                    tags={"location": location},
                                    fields=data,
                                    timestamp=sim_time
                                )
                            elif "valve" in parts and "set" in parts:
                                # home/bureau/valve/set
                                location = parts[1]
                                
                                self.influx_service.write_data(
                                    measurement="actuators",
                                    tags={"location": location, "type": "valve"},
                                    fields=data
                                )
                        elif "sys" in parts and "clock" in parts:
                            # home/sys/clock -> 2023-01-01T12:00:00
                            # This is the master clock
                            if hasattr(self, 'mpc_service') and self.mpc_service:
                                self.mpc_service.update_time(payload_str)
                    except json.JSONDecodeError as e:
                        # Handle raw strings like the clock
                        if "clock" in topic:
                            # Payload is ISO string e.g. "2023..."
                            if hasattr(self, 'mpc_service') and self.mpc_service:
                                self.mpc_service.update_time(payload_str)
                        else:
                            logger.error(f"JSON Decode Error: {e}")
                        
        except Exception as e:
            logger.error(f"MQTT Error: {e}")
            # Simple reconnection logic could be added here or relied on orchestration restart
            await asyncio.sleep(5)
