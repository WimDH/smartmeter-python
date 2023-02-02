from smartmeter.utils import child_logger
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from typing import Dict, List
from smartmeter.utils import convert_timestamp
from time import monotonic
import multiprocessing as mp


class DbInflux:
    """
    Connect to Influx and write data.
    TODO: if influxdb is unreachable, cache the result and
          write them to the DB when the connection is back up.
    """

    def __init__(
        self,
        log_q: mp.Queue,
        url: str,
        token: str,
        org: str,
        bucket: str,
        verify_ssl: bool = True,
        timeout: int = 30 * 1000,  # milliseconds
        ssl_ca_cert: str = None,
    ) -> None:

        self.url = url
        self.log = child_logger(log_q)
        self.token = token
        self.org = org
        self.bucket = bucket
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.ssl_ca_cert = ssl_ca_cert
        self.start_time = monotonic()
        self.batch = []

    async def write(self, data: Dict, upload_interval: int = 0) -> None:
        """
        Write a telegram to an influx bucket.
        """
        if upload_interval > 0:
            self.batch.append(self.craft_json(data))
        else:
            self.batch = [self.craft_json(data)]

        async with InfluxDBClientAsync(
            url=self.url,
            token=self.token,
            org=self.org,
            timeout=self.timeout,
            verify_ssl=self.verify_ssl,
            ssl_ca_cert=self.ssl_ca_cert,
        ) as db:
            write_api = db.write_api()
            await write_api.write(bucket=self.bucket, record=self.batch, org=self.org)

    def craft_json(self, data: Dict) -> List[Dict]:
        """
        Prepare the data to be written to InfluxDB.
        """

        self.log.debug("Crafting Influx datapoints.")

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
        self.log.debug(f"Electricity data point: {e_data}")

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
        self.log.debug(f"Gas data point: {g_data}")

        # Load data.
        l_data = {
            "measurement": "load",
            "tags": {},
            "time": convert_timestamp(data.get("timestamp", "")),
            "fields": {"load_on": data.get("load_status", 0)},
        }
        self.log.debug(f"Load data point: {l_data}")

        return [e_data, g_data, l_data]
