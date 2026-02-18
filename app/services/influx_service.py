from typing import Optional
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

    def write_data(self, measurement: str, tags: dict, fields: dict, timestamp=None):
        """Write a data point to InfluxDB."""
        try:
            point = Point(measurement)
            if timestamp:
                point.time(timestamp)
            for tag, value in tags.items():
                point.tag(tag, value)
            for field, value in fields.items():
                point.field(field, value)
            
            self.write_api.write(bucket=settings.INFLUXDB_BUCKET, org=settings.INFLUXDB_ORG, record=point)
            logger.debug(f"Written to InfluxDB: {measurement} {tags} {fields}")
        except Exception as e:
            logger.error(f"InfluxDB Write Error: {e}")

        except Exception as e:
            logger.error(f"InfluxDB Write Error: {e}")

    def get_latest_data(self, measurement: str, location: str, field: str) -> Optional[float]:
        """Get the last known value for a specific field."""
        query = f'''
        from(bucket: "{settings.INFLUXDB_BUCKET}")
            |> range(start: -30d)
            |> filter(fn: (r) => r["_measurement"] == "{measurement}")
            |> filter(fn: (r) => r["location"] == "{location}")
            |> filter(fn: (r) => r["_field"] == "{field}")
            |> last()
        '''
        try:
            result = self.client.query_api().query(org=settings.INFLUXDB_ORG, query=query)
            if result and len(result) > 0 and len(result[0].records) > 0:
                return result[0].records[0].get_value()
            return None
        except Exception as e:
            logger.error(f"InfluxDB Read Error: {e}")
            return None
        self.client.close()
