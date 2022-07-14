import pytest
import sys
import os
import pathlib
from gpiozero import Device
from gpiozero.pins.mock import MockFactory
from time import sleep

sys.path.append(
    os.path.abspath(os.path.join(pathlib.Path(__file__).parent.resolve(), ".."))
)
from smartmeter.aux import LoadManager, Timer, Load, gpio

Device.pin_factory = MockFactory()


def test_timer_elapsec_when_not_started():
    """
    Test if elapsed returns -1 when the timer is not set.
    """
    t = Timer()

    assert t.elapsed == -1


@pytest.mark.parametrize("result",  [True, False])
def test_load_status(result):
    """
    Test if we can get the status of the load: 1 if the load is on, 0 if the load is off.
    Also test if we can get the is_on and is_off values.
    """
    load = Load(pin=24, name="test load", max_power=2300)

    load.on() if result is True else load.off
    assert load.status == (1 if result else 0)
    assert load.is_on == result
    assert load.is_off is not result


def test_loadmanager():
    """
    Test the loadmanager.
    """
    lm = LoadManager(
        max_consume=500,  # Watt
        max_inject=1500,  # Watt
        consume_time=3,  # seconds
        inject_time=3    # seconds
    )

    lm.process(data={"actual_total_injection": 2, "actual_total_consumption": 0})
    assert lm.timer.is_started is True
    assert lm.timer.timer_type == "inject"
    sleep(1)
    assert lm.timer.elapsed >= 1

    lm.process(data={"actual_total_injection": 1, "actual_total_consumption": 0})
    assert lm.timer.is_started is True
    assert lm.timer.timer_type == "inject"
    assert lm.timer.elapsed < 1

    lm.process(data={"actual_total_injection": 2, "actual_total_consumption": 0})
    sleep(3)

    lm.process(data={"actual_total_injection": 2, "actual_total_consumption": 0})
    assert lm.timer.is_started is False
    assert lm.load.is_on

    lm.process(data={"actual_total_injection": 0, "actual_total_consumption": 0.1})
    assert lm.timer.is_started is False
    assert lm.load.is_on

    lm.process(data={"actual_total_injection": 0, "actual_total_consumption": 0.5})
    assert lm.timer.is_started is True
    assert lm.timer.timer_type == "consume"
    sleep(1)
    assert lm.timer.elapsed >= 1

    lm.process(data={"actual_total_injection": 0, "actual_total_consumption": 0.1})
    assert lm.timer.is_started is True
    assert lm.timer.timer_type == "consume"
    assert lm.timer.elapsed < 1

    lm.process(data={"actual_total_injection": 0, "actual_total_consumption": 0.6})
    sleep(3)

    lm.process(data={"actual_total_injection": 0, "actual_total_consumption": 0.55})
    assert lm.timer.is_started is False
    assert lm.load.is_off


