from typing import Dict
from unittest.mock import Mock
import pytest
import os
import json
from smartmeter.influx import convert_timestamp, DbInflux, InfluxDBClient


def load_json_datapoints() -> json:
    """Load the datapoints from a JSON file."""
    data = None
    with open(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "testdata/datapoints.json"
        )
    ) as jf:
        data = json.load(jf)

    return data


def fake_influx_connection() -> DbInflux:
    return DbInflux(
        host="127.0.0.1",
        path="",
        username="test",
        password="test",
        database="test",
    )


@pytest.fixture
def valid_input_data() -> Dict:
    return {
        "local_timestamp": "2021-11-07T11:37:12.061909",
        "timestamp": "211024195235S",
        "total_consumption_day": 4248.198,
        "total_consumption_night": 6615.642,
        "total_injection_day": 2278.958,
        "total_injection_night": 908.264,
        "actual_tariff": 2,
        "actual_total_consumption": 0.507,
        "actual_total_injection": 0.0,
        "actual_l1_consumption": 0.245,
        "actual_l2_consumption": 0.0,
        "actual_l3_consumption": 0.261,
        "actual_l1_injection": 0.0,
        "actual_l2_injection": 0.0,
        "actual_l3_injection": 0.0,
        "l1_voltage": 227.1,
        "l2_voltage": 0.0,
        "l3_voltage": 226.7,
        "l1_current": 1.53,
        "l2_current": 1.94,
        "l3_current": 1.65,
        "total_gas_consumption": 3775.342,
        "gas_timestamp": "211024195005S",
    }


def test_convert_timestamp() -> None:
    """Test the conversion of a timestamp to iso8601."""
    result = convert_timestamp("211024195235S")
    assert result == "2021-10-24T19:52:35+02:00"


def test_craft_json(valid_input_data) -> None:
    """Test the generation of the JSON body to be sent to influxDB."""
    e_result = {
        "measurement": "electricity",
        "tags": {},
        "time": "2021-10-24T19:52:35+02:00",
        "fields": {
            "total_consumption_day": 4248.198,
            "total_consumption_night": 6615.642,
            "total_injection_day": 2278.958,
            "total_injection_night": 908.264,
            "actual_tariff": 2,
            "actual_total_consumption": 0.507,
            "actual_total_injection": 0.0,
            "actual_l1_consumption": 0.245,
            "actual_l2_consumption": 0.0,
            "actual_l3_consumption": 0.261,
            "actual_l1_injection": 0.0,
            "actual_l2_injection": 0.0,
            "actual_l3_injection": 0.0,
            "l1_voltage": 227.1,
            "l2_voltage": 0.0,
            "l3_voltage": 226.7,
            "l1_current": 1.53,
            "l2_current": 1.94,
            "l3_current": 1.65,
        },
    }
    g_result = {
        "measurement": "gas",
        "tags": {},
        "time": "2021-10-24T19:50:05+02:00",
        "fields": {"total_gas_consumption": 3775.342},
    }
    l_result = {
        "fields": {"load_on": 0},
        "measurement": "load",
        "tags": {},
        "time": "2021-10-24T19:52:35+02:00",
    }

    result = DbInflux.craft_json(valid_input_data)

    assert result == [e_result, g_result, l_result]


def test_influxdb_ping() -> None:
    """Test if we can check if the influxDB is reachable or not"""

    db = fake_influx_connection()

    InfluxDBClient.ping = Mock()
    InfluxDBClient.ping.return_value = ' '
    assert db.is_reachable is True

    InfluxDBClient.ping = Mock()
    InfluxDBClient.ping.side_effect = ConnectionError("mocked error!")
    assert db.is_reachable is False


def test_influxdb_write() -> None:
    """
    Test if we can write a list of datapoints to Influx.
    TODO: improve test
    """

    data = load_json_datapoints()

    db = fake_influx_connection()
    InfluxDBClient.write_points = Mock()
    InfluxDBClient.write_points.return_value = None

    result = db.write(data)

    assert result is None
