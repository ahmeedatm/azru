import logging
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from app.config import settings

logger = logging.getLogger(__name__)

class InfluxService:
    def __init__(self):
        self.client = InfluxDBClient(
            url=settings.INFLUXDB_URL,
            token=settings.INFLUXDB_TOKEN,
            org=settings.INFLUXDB_ORG
        )
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

    def write_data(self, measurement: str, tags: dict, fields: dict):
        """Write a data point to InfluxDB."""
        try:
            point = Point(measurement)
            for tag, value in tags.items():
                point.tag(tag, value)
            for field, value in fields.items():
                point.field(field, value)
            
            self.write_api.write(bucket=settings.INFLUXDB_BUCKET, org=settings.INFLUXDB_ORG, record=point)
            logger.debug(f"Written to InfluxDB: {measurement} {tags} {fields}")
        except Exception as e:
            logger.error(f"InfluxDB Write Error: {e}")

    def close(self):
        self.client.close()
