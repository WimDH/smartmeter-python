import pytest
import sys
import os
import pathlib
from gpiozero import Device, DigitalOutputDevice
from gpiozero.pins.mock import MockFactory
from time import time, sleep

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


def test_load_switch_on_off_power():
    """"""
    l = Load(pin=1, name="test", max_power=1000, switch_threshold=80)

    assert l.switch_on_power == 800
    assert l.switch_off_power == 200


def test_loadmanager_process_no_action(monkeypatch):
    """
    Test if we process data that is between both thresholds:
        - timer is not set
        - load is not swicthed on
    Start conditions:
        - timer is not set
        - load is off
    """
    testdata = {"actual_total_injection": 10, "actual_total_consumption": 0}
    monkeypatch.setattr(gpio, "DigitalOutputDevice", DigitalOutputDevice)

    lm = LoadManager()
    lm.process(data=testdata)

    assert lm.timer.is_started is False
    assert lm.timer.elapsed == -1


@pytest.mark.parametrize(
    "testdata, timer_state, timer_threshold",
    [
        ({"actual_total_injection": 1500, "actual_total_consumption": 0}, True, "upper"),
        ({"actual_total_injection": 0, "actual_total_consumption": 500}, True, "lower")
    ]

)
def test_loadmanager_set_timer(monkeypatch, testdata, timer_state, timer_threshold):
    """
    Test if the timer is started when we cross the upper or lower threshold.
    """
    monkeypatch.setattr(gpio, "DigitalOutputDevice", DigitalOutputDevice)

    lm = LoadManager()
    lm.process(data=testdata)

    assert lm.timer.is_started is timer_state
    assert lm.timer.threshold == timer_threshold
    sleep(1)
    assert lm.timer.elapsed >= 1

@pytest.mark.parametrize(
    "testdata, timer_state, timer_threshold",
    [
        ({"actual_total_injection": 900, "actual_total_consumption": 0}, True, "upper"),
        ({"actual_total_injection": 0, "actual_total_consumption": 50}, True, "lower")
    ]

)
def test_loadmanager_reset_timer(monkeypatch):
    """
    Test if the timer is reset when we are crossing the previously set threshold.
    """
    monkeypatch.setattr(gpio, "DigitalOutputDevice", DigitalOutputDevice)

    lm = LoadManager()
    lm.process(data=testdata)    