import logging
from influxdb import InfluxDBClient
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
        host: str,
        path: str,
        username: str,
        password: str,
        database: str,
        verify_ssl: bool = True,
        timeout: int = 30 * 1000,  # milliseconds
        ssl_ca_cert: str = None,
    ) -> None:

        self.host = host
        self.path = path
        self.username = username
        self.password = password
        self.database = database
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.ssl_ca_cert = ssl_ca_cert

        self.db = InfluxDBClient(
            host=self.host,
            #path=self.path,
            username=self.username,
            password=self.password,
            database=self.database,
            timeout=self.timeout,
            verify_ssl=self.verify_ssl,
            # ssl_ca_cert=self.ssl_ca_cert,
        )

    def write(self, data: List) -> None:
        """
        Write datapoints to InfluxDB.
        # TODO: add counters for datapoints that are successfully written!
        # TODO: return how many records were successfully written.
        # TODO: logging.
        """
        points_list: List = []
        for entry in data:
                points_list += self.craft_json(entry)

        self.db.write_points(points=points_list)

    @property
    def is_reachable(self) -> bool:
        """
        Return True if the InfluxDB is reachable, else False.
        Log the error message is the DB is unreachable.
        """
        try:
            return True if self.db.ping() else False
        except ConnectionError:
            LOG.critical("Influx database at {} is not reachable!".format(self.host))
            return False

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
            "fields": {"load_on": data.get("load_status")},
        }

        LOG.debug(f"Load data point: {l_data}")

        return [e_data, g_data, l_data]
