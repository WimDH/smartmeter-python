import logging
from influxdb import InfluxDBClient
from typing import Dict, List, Tuple
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
        username: str,
        password: str,
        database: str,
        verify_ssl: bool = True,
        timeout: int = 30 * 1000,  # milliseconds
        ssl_ca_cert: str = None,
    ) -> None:

        self.url = url
        self.username = username
        self.password = password
        self.database = database
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.ssl_ca_cert = ssl_ca_cert

    def write(self, data: Dict) -> None:
        """
        Write a telegram to InfluxDB.
        # TODO: add counters for datapoints that are successfully written!
        # TODO: return how manu records were successfully written.
        # TODO: logging.
        """
        record_list: List = []
        for record in self.craft_json(data):
            record_list.append(record)

        db = InfluxDBClient(
            url=self.url,
            username=self.username,
            password=self.password,
            database=self.database,
            timeout=self.timeout,
            verify_ssl=self.verify_ssl,
            ssl_ca_cert=self.ssl_ca_cert
        )
        db.write_points(points=record_list)

    @staticmethod
    def craft_json(data: Dict) -> Tuple[Dict, Dict]:
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

        return (e_data, g_data)
