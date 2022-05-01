# import asyncio
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from logging import getLogger
from typing import Dict, List, Tuple
from smartmeter.utils import convert_timestamp

LOG = getLogger(".")


class DbInflux:
    """
    Connect to Influx and write data.
    Todo: if influxdb is unreachable, cache the result and
          write them to the DB whet the connection is back up.
    """

    def __init__(
        self,
        verify_ssl: bool = False,
        database: str = "smartmeter",
    ) -> None:

        self.influx_connection = None

    def connect(self) -> None:
        """Connect to InfluxDB."""

        self.influx_connection = InfluxDBClientAsync(

        )

    def write(self, data: Dict) -> Tuple[bool, ...]:
        """
        Write a telegram to influx.
        Return the status as a list of booleans for each datapoint written.
        """

        e_data: Dict
        g_data: Dict
        status: List[bool] = []

        (e_data, g_data) = self.craft_json(data)

        for (measurement, measurement_data) in [
            ("Electricity", e_data),
            ("Gas", g_data),
        ]:

            if (
                self.conn.write_points(
                    [
                        measurement_data,
                    ]
                )
                is True
            ):
                LOG.debug(
                    f"{measurement} data point successfully written: {measurement_data}"
                )
                status.append(True)
            else:
                LOG.warning(f"{measurement} data point not written: {measurement_data}")
                status.append(False)

        return tuple(status)

    @staticmethod
    def craft_json(data: Dict) -> Tuple[Dict, Dict]:
        """
        Create a valid JSON for the influxDB out of the data we got.
        """

        LOG.debug("Crafting Influx JSON datapoints.")

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
