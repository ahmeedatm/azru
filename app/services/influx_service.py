from typing import Optional
import logging
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from influxdb_client import InfluxDBClient, Point
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)

class InfluxService:
    def __init__(self):
        self.url = settings.INFLUXDB_URL
        self.token = settings.INFLUXDB_TOKEN
        self.org = settings.INFLUXDB_ORG
        self.async_client: Optional[InfluxDBClientAsync] = None

    def _get_async_client(self):
        if self.async_client is None:
            self.async_client = InfluxDBClientAsync(
                url=self.url,
                token=self.token,
                org=self.org
            )
        return self.async_client

    async def write_data(self, measurement: str, tags: dict, fields: dict, timestamp=None):
        """Write a data point to InfluxDB asynchronously."""
        try:
            point = Point(measurement)
            if timestamp:
                point.time(timestamp)
            for tag, value in tags.items():
                point.tag(tag, value)
            for field, value in fields.items():
                point.field(field, value)
            
            client = self._get_async_client()
            write_api = client.write_api()
            await write_api.write(bucket=settings.INFLUXDB_BUCKET, org=settings.INFLUXDB_ORG, record=point)
            logger.debug(f"Written to InfluxDB: {measurement} {tags} {fields}")
        except Exception as e:
            logger.error(f"InfluxDB Write Error: {e}")

    async def get_latest_data(self, measurement: str, location: str, field: str) -> Optional[float]:
        """Get the last known value for a specific field asynchronously."""
        query = f'''
        from(bucket: "{settings.INFLUXDB_BUCKET}")
            |> range(start: -30d)
            |> filter(fn: (r) => r["_measurement"] == "{measurement}")
            |> filter(fn: (r) => r["location"] == "{location}")
            |> filter(fn: (r) => r["_field"] == "{field}")
            |> last()
        '''
        try:
            client = self._get_async_client()
            query_api = client.query_api()
            result = await query_api.query(org=settings.INFLUXDB_ORG, query=query)
            result = await query_api.query(org=settings.INFLUXDB_ORG, query=query)
            if result:
                for table in result:
                    for record in table.records:
                        return float(record.get_value())
            return None
        except Exception as e:
            logger.error(f"InfluxDB Read Error: {e}")
            return None
            
    def clear_database(self, start="1970-01-01T00:00:00Z", stop="2100-01-01T00:00:00Z"):
        """Delete all data from the bucket between start and stop times."""
        try:
            logger.info(f"Clearing InfluxDB bucket '{settings.INFLUXDB_BUCKET}' from {start} to {stop}")
            with InfluxDBClient(url=self.url, token=self.token, org=self.org) as sync_client:
                delete_api = sync_client.delete_api()
                delete_api.delete(
                    start, stop,
                    predicate="",
                    bucket=settings.INFLUXDB_BUCKET,
                    org=settings.INFLUXDB_ORG
                )
            logger.info("Database cleared successfully.")
        except Exception as e:
            logger.error(f"InfluxDB Delete Error: {e}")

    async def close(self):
        if self.async_client:
            await self.async_client.close()
            self.async_client = None
