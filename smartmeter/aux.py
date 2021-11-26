from logging import getLogger
from typing import Optional, Union
from time import time

try:
    import gpiozero as gpio
except ImportError:
    pass

from typing import Dict


LOG = getLogger(".")


class Load:
    """
    Defines a load.
    For Pin numbering: https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering
    """

    def __init__(self, pin: int, name: str, max_power: int) -> None:
        self.load = gpio.DigitalOutputDevice(
            pin=pin, initial_value=False
        )  # See pin numbering
        self.gpio_ping = pin
        self.name = name
        self.max_power = max_power

    @property
    def status(self):
        """
        Return 0 or 1.
        0 if the load is off.
        1 if the load is on.
        """
        state = "ON" if self.load.status() == 1 else "OFF"
        LOG.debug(f"{self.name} on GPIO pin {self.gpio_pin} is {state}.")
        return self.load.status()

    def on(self):
        """Switches the load on (set the pin high."""
        LOG.info(f"Turning {self.name} on GPIO pin {self.gpio_pin} ON.")
        self.load.on()

    def off(self):
        """Switches the load on (set the pin high."""
        LOG.info(f"Turning {self.name} on GPIO pin {self.gpio_pin} OFF.")
        self.load.off()

    @property
    def current_power(self):
        """
        Return how much power the load draws in Watt.
        For now it returns the max_power, until a current sensing mechanism is in place.
        """
        return self.max_power


class Aux:
    """
    Switching loads.
    """

    def __init__(self) -> None:
        self.stability_timer: Union[float, None] = None

    def _reset_stability_timer(self):
        """Reset the timer."""
        self.stability_timer = None

    def _start_stability_timer(self):
        """Start counting."""
        self.stability_timer = time()

    def _elapsed_stability_timer(self):
        """return the number of seconds sinds the timer was started."""
        return time() - self.stability_timer

    def _stability_timer_is_set(self):
        """Return True is set, else False."""
        return self.stability_timer is not None

    def load_manager(self, data: Dict) -> None:
        """
        Swicthes loads depending on the power we put on the grid. For the moment only locally connected loads.
        """
        actual_grid_injection = data.get("actual_l1_injection", 0)
        actual_grid_consumption = data.get("actual_l1_consumption", 0)
        # Set the load to manage.
        load1 = Load(pin=17, name="car charger", max_power=230 * 6)

        while True:

            # Start the satbility timer if:
            #  - the grid load is above the upper threshold, or below the lower threshold
            #  - and the timer is not set.
            if (
                actual_grid_injection > load1.max_power
                or actual_grid_consumption > load1.max_power
            ) and self._stability_timer_is_set() is None:
                self._start_stability_timer()

            # If the timer is running and the power drops below the load's max power - 5%.
            elif (
                actual_grid_injection < (load1.max_power * 0.95)
                and self._stability_timer_is_set
            ):
                self._reset_stability_timer

            # If the grid power is above the max power of the load, and it did not drop, switch on the load (300sec).
            # Reset the timer.
            elif (
                actual_grid_load > load1.max_power
                and self._elapsed_stability_timer <= 300
            ):
                load1.on()
                self._reset_stability_timer()
