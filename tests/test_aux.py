import pytest
import configparser
from gpiozero import Device
from gpiozero.pins.mock import MockFactory
from smartmeter.aux import LoadManager, Timer, Load

Device.pin_factory = MockFactory()


def test_timer_elapsec_when_not_started():
    """
    Test if elapsed returns -1 when the timer is not set.
    """
    t = Timer()

    assert t.elapsed == -1


@pytest.mark.parametrize("result", [True, False])
def test_load_status(result):
    """
    Test if we can get the status of the load: 1 if the load is on, 0 if the load is off.
    Also test if we can get the is_on and is_off values.
    """
    load = Load(name="test load", max_power=2300, switch_on=10, switch_off=10, hold_timer=10)

    load.on() if result is True else load.off
    assert load.status == (1 if result else 0)
    assert load.is_on == result
    assert load.is_off is not result


def test_loadmanager_add_load():
    """
    Test the loadmanager.
    """
    load_cfg = configparser.ConfigParser()
    load_cfg['load:aux'] = {
        "max_power": "2300",
        "switch_on": "75",
        "switch_off": "10",
        "hold_timer": "10"
    }

    lm = LoadManager()
    lm.add_load(load_cfg['load:aux'])

    assert len(lm.load_list) == 1
