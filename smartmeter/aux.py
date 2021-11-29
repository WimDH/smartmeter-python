from logging import getLogger
from typing import Union, Dict
from time import time

try:
    import gpiozero as gpio
except ImportError:
    pass

LOG = getLogger(".")
VALID_THRESHOLD_NAMES = ["upper", "lower"]

class Load:
    """
    Defines a load.
    For Pin numbering: https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering
    switch_threshold is in percent and represents the amount of power that has to come from the solar panels.
    """

    def __init__(
        self, pin: int, name: str, max_power: int, switch_threshold: int
    ) -> None:
        self._load = gpio.DigitalOutputDevice(
            pin=pin, initial_value=False
        )  # See pin numbering
        self.gpio_pin = pin
        self.name = name
        self.max_power = max_power
        self.switch_threshold = switch_threshold

    @property
    def status(self):
        """
        Return 0 or 1.
        0 if the load is off.
        1 if the load is on.
        """
        state = "ON" if self._load.value == 1 else "OFF"
        LOG.debug(f"{self.name} on GPIO pin {self.gpio_pin} is {state}.")
        return self._load.value

    def on(self):
        """Switches the load on (set the pin high."""
        LOG.info(f"Turning {self.name} on GPIO pin {self.gpio_pin} ON.")
        self._load.on()

    def off(self):
        """Switches the load on (set the pin high."""
        LOG.info(f"Turning {self.name} on GPIO pin {self.gpio_pin} OFF.")
        self._load.off()

    @property
    def current_power(self):
        """
        Return how much power the load draws in Watt.
        For now it returns the max_power, until a current sensing mechanism is in place.
        """
        return self.max_power

    @property
    def switch_on_power(self):
        """ Power in watt to be injected before the load can be switched on."""
        return self.max_power * self.switch_threshold / 100
    
    @property
    def switch_off_power(self):
        """Power to be consumed before the load is swicthed off."""
        return self.max_power * (100 - self.switch_threshold) / 100


class Timer:
    """
    Represents a timer that count how long the actual power crossed it's threshold.
    Two thresholds are valid:
        1. "upper": the upper threshold, which defines the maximum injected power.
        2. "lower": the lower threshold, which defines the maximum consumed power.
    """
    def __init__(self) -> None:
        self._start_time: Union[float, None] = None
        self.threshold: Union[str, None] = None

    def start(self, threshold: str) -> None:
        """
        Start the timer.
        """
        if threshold not in VALID_THRESHOLD_NAMES:
            raise ValueError(f"Threshold not in {VALID_THRESHOLD_NAMES}")

        LOG.debug("Timer: starting timer for {threshold} threshold.")
        self._start_time = time()
        self.threshold = threshold

    def stop(self) -> None:
        """
        Stop the timer.
        """
        LOG.debug("Timer: stopping timer.")
        self._start_time = None

    def reset(self) -> None:
        """
        Set the timer to the current time, overwriting the previous value.
        It's actually the same as starting the timer.
        """
        LOG.debug("Timer: resetting timer.")
        self._start_time = time()

    @property
    def elapsed(self) -> int:
        """
        Return the number of seconds since the timer was started.
        """
        if self._start_time is None:
            LOG.error("Timer: cannot calculate elapsed time, timer is not started!")
            return -1

        elapsed_seconds = int(time() - self._start_time)
        LOG.debug(f"Timer: elaspsed time is {elapsed_seconds} seconds.")
        return elapsed_seconds

    @property
    def is_started(self):
        """return True if the timer is started, else false."""
        return self._start_time is not None


class LoadManager:
    """ Manages the lifecycle of a connected load."""
    def __init__(self) -> None:
        # Setup the load(s)
        self.load = Load(pin=17, name="car charger", max_power=230 * 6, switch_threshold=75)
        self.timer = Timer()

    def process(self, data: Dict) -> None:
        """
        Process the data coming from the digital meter, and switch the load if needed.
        """
        actual_injected = data.get("actual_total_injection", 0)
        actual_consumed = data.get("actual_total_consumption", 0)
        LOG.debug(f"Load manager: Processing data: actual injected={actual_injected}W, actual consumed={actual_consumed}W.")

        # Start the timer if the actual power is crossing the upper threshold.
        if not self.timer.is_started and actual_injected >= self.load.switch_on_power:
            LOG.debug("Loadmanager: upper threshold crossed, started the stablity timer.")
            self.timer.start(threshold="upper")
            return

        # Start the timer if the actual power is crossing the lower threshold.
        if not self.timer.is_started and actual_consumed >= self.load.switch_off_power:
            LOG.debug("Loadmanager: lower threshold crossed, started the stablity timer.")
            self.timer.start(threshold="lower")
            return

        # Reset the timer if the actual power is between both thresholds, or when is is crossing the oposite threshold.
        if (
            self.timer.is_started and
            (
                actual_injected < self.load.switch_on_power and actual_consumed == 0
                or actual_consumed < self.load.switch_off_power and actual_injected == 0
            )
        ):
            self.timer.reset()
            return

        return