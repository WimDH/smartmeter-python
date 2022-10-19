import logging
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from influxdb_client import WriteOptions
from typing import Dict, List
from smartmeter.utils import convert_timestamp


LOG = logging.getLogger()


class DbInflux:
    """
    Connect to Influx and write data.
    TODO: if influxdb is unreachable, cache the result and
          write them to the DB when the connection is back up.
    """

    def __init__(
        self,
        url: str,
        token: str,
        org: str,
        bucket: str,
        verify_ssl: bool = True,
        timeout: int = 30 * 1000,  # milliseconds
        ssl_ca_cert: str = None,
    ) -> None:

        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.ssl_ca_cert = ssl_ca_cert

    async def write(self, data: Dict) -> None:
        """
        Write a telegram to an influx bucket.
        TODO: support batching from the client itself.
        """
        async with InfluxDBClientAsync(
            url=self.url,
            token=self.token,
            org=self.org,
            timeout=self.timeout,
            verify_ssl=self.verify_ssl,
            ssl_ca_cert=self.ssl_ca_cert,
        ) as db:
            with db.write_api(
                write_options=WriteOptions(
                    batch_size=60,
                    flush_interval=60000,
                    jitter_interval=2000,
                    retry_interval=5000,
                    max_retries=5,
                    max_retry_delay=30000,
                    exponential_base=2,
                )
            ) as write_api:
                await write_api.write(
                    bucket=self.bucket, record=self.craft_json(data), org=self.org
                )

    @staticmethod
    def craft_json(data: Dict) -> List[Dict]:
        """
        Prepare the data to be written to InfluxDB.
        """

        LOG.debug("Crafting Influx datapoints.")

        # Electricity data.
        e_data = {
            "measurement": "electricity",
            "tags": {},
            "time": convert_timestamp(data.get("timestamp", "")),
            "fields": {
                key: value
                for (key, value) in data.items()
                if ("timestamp" not in key and "gas" not in key)
            },
        }
        LOG.debug(f"Electricity data point: {e_data}")

        # Gas data.
        g_data = {
            "measurement": "gas",
            "tags": {},
            "time": convert_timestamp(data.get("gas_timestamp", "")),
            "fields": {
                key: value
                for (key, value) in data.items()
                if ("timestamp" not in key and "gas" in key)
            },
        }
        LOG.debug(f"Gas data point: {g_data}")

        # Load data.
        l_data = {
            "measurement": "load",
            "tags": {},
            "time": convert_timestamp(data.get("timestamp", "")),
            "fields": {"load_on": data.get("load_status", 0)},
        }
        LOG.debug(f"Load data point: {l_data}")

        return [e_data, g_data, l_data]
