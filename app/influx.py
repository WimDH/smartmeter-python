import influxdb
from logging import getLogger
from typing import Dict

LOG = getLogger(".")


def convert_timestamp(timestamp: str) -> str:
    """
    Convert a timestamp in the for of '211024195235S' in iso8601 format.
    YYMMDDHHMMSS[WS]
    Last letter can be a S (summer) or a W (winter).
    """
    tz_map: Dict = {"S": "02:00", "W": "01:00"}
    year: str = "20" + timestamp[0:2]
    month: str = timestamp[2:4]
    day: str = timestamp[4:6]
    hour: str = timestamp[6:8]
    minute: str = timestamp[8:10]
    second: str = timestamp[10:12]
    tz: str = tz_map[timestamp[-1]]

    return f"{year}-{month}-{day}T{hour}:{minute}:{second}+{tz}"


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
        e_result = True
        g_result = True

        if (self.conn.write_points([e_data, ]) is True):
            LOG.debug(f"Electricity data point successfully written: {e_data}")
        else:
            LOG.warning("Electricity data point not written: {e_data}")
            e_result = False

        if (self.conn.write_points([g_data, ]) is True):
            LOG.debug(f"Gas data point successfully written: {g_data}")
        else:
            LOG.warning("Gas data point not written: {g_data}")
            g_result = False

        return e_result, g_result

    @staticmethod
    def craft_json(data) -> Dict:
        """
        Create a valid JSON for the influxDB out of the data we got.
        """
        e_data = {}
        g_data = {}
        # Process electricity data.
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

        # Process gas data.
        g_data = {
            "measurement": "electricity",
            "tags": {},
            "time": convert_timestamp(data.get("gas_timestamp")),
            "fields": {
                key: value
                for (key, value) in data.items()
                if ("timestamp" not in key and "gas" in key)
            },
        }

        return (e_data, g_data)
