import pytest
import configparser
from gpiozero import Device
from gpiozero.pins.mock import MockFactory
from smartmeter.aux import LoadManager, Load

Device.pin_factory = MockFactory()


@pytest.mark.parametrize("result", [True, False])
def test_load_status(result):
    """
    Test if we can get the status of the load: 1 if the load is on, 0 if the load is off.
    Also test if we can get the is_on and is_off values.
    """
    load = Load(
        name="test load", max_power=2300, switch_on=10, switch_off=10, hold_timer=10
    )

    load.on() if result is True else load.off
    assert load.status == (1 if result else 0)
    assert load.is_on == result
    assert load.is_off is not result


def test_loadmanager_add_load():
    """
    Test the loadmanager.
    """
    load_cfg = configparser.ConfigParser()
    load_cfg["load:aux"] = {
        "max_power": "2300",
        "switch_on": "75",
        "switch_off": "10",
        "hold_timer": "10",
    }

    lm = LoadManager()
    lm.add_load(load_cfg["load:aux"])

    assert len(lm.load_list) == 1


@pytest.mark.parametrize("injected,consumed", [(0, 0), (2000, 0), (3000, 0)])
def test_loadmanager_process(consumed, injected):
    """
    Testing the loadmanager processing the data received from the digital meter.
    """
    load_cfg = configparser.ConfigParser()
    load_cfg["load:aux"] = {
        "max_power": "2300",
        "switch_on": "75",
        "switch_off": "10",
        "hold_timer": "10",
    }

    lm = LoadManager()
    lm.add_load(load_cfg["load:aux"])

    processed = lm.process(
        {"actual_total_injection": injected, "actual_total_consumption": consumed}
    )

    assert processed == {"aux": False}
