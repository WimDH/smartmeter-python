from typing import Dict
import pytest
import os
import json
from smartmeter.influx import convert_timestamp


def load_json_datapoints() -> json:
    """Load the datapoints from a JSON file."""
    data = None
    with open(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "testdata/datapoints.json"
        )
    ) as jf:
        data = json.load(jf)

    return data


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
