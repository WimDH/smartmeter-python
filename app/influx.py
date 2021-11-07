import influxdb
from logging import getLogger
from typing import Dict, List, Tuple
from app.utils import convert_timestamp, calculate_timestamp_drift

LOG = getLogger(".")


class DbInflux:
    """
    Connect to Influx and write data.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8086,
        ssl: bool = False,
        verify_ssl: bool = False,
        database: str = "smartmeter",
        username: str = "root",
        password: str = "root",
    ) -> None:
        self.host = host
        self.port = port
        self.ssl = ssl
        self.verify_ssl = verify_ssl
        self.database = database
        self.username = username
        self.password = password
        self.conn = None

    def connect(self) -> None:
        """Connect to InfluxDB."""

        self.conn = influxdb.InfluxDBClient(
            host=self.host,
            port=self.port,
            ssl=self.ssl,
            verify_ssl=self.verify_ssl,
            database=self.database,
            username=self.username,
            password=self.password,
        )

    def write(self, data: Dict) -> None:
        """write a telegram to influx."""
        e_data, g_data = self.craft_json(data)
        status: List = []

        for measurement, data in [("Electricity", e_data), ("Gas", g_data)]:

            if (
                self.conn.write_points(
                    [
                        data,
                    ]
                )
                is True
            ):
                LOG.debug(f"{measurement} data point successfully written: {data}")
                status.append(True)
            else:
                LOG.warning(f"{measurement} data point not written: {data}")
                status.append(False)

        return status

    @staticmethod
    def craft_json(data: Dict) -> Tuple[Dict]:
        """Create a valid JSON for the influxDB out of the data we got."""
        LOG.debug("Crafting Influx JSON datapoints.")

        # Electricity data.
        e_data = {
            "measurement": "electricity",
            "tags": {},
            "time": convert_timestamp(data.get("timestamp")),
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
            "time": convert_timestamp(data.get("gas_timestamp")),
            "fields": {
                key: value
                for (key, value) in data.items()
                if ("timestamp" not in key and "gas" in key)
            },
        }

        LOG.debug(f"Gas data point: {g_data}")

        return (e_data, g_data)
