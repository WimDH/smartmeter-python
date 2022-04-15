from logging import getLogger
from typing import Union, Dict
from time import time

try:
    import board
    import displayio
    # import busio
    import adafruit_displayio_ssd1306

    displayio.release_displays()

except ImportError:
    pass

try:
    import gpiozero as gpio
except ImportError:
    pass

LOG = getLogger(".")
THRESHOLD_NAMES = ["upper", "lower"]


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
        self.gpio_pin: int = pin
        self.name: str = name
        self.max_power: float = max_power
        self.switch_threshold: int = switch_threshold
        self.state_start_time: Union[int, None] = None

    @property
    def status(self) -> int:
        """
        Return 0 or 1.
        0 if the load is off.
        1 if the load is on.
        """
        state: str = "ON" if self._load.value == 1 else "OFF"
        LOG.debug(f"{self.name} on GPIO pin {self.gpio_pin} is {state}.")
        return self._load.value

    def on(self) -> None:
        """Switches the load on (set the pin high."""
        LOG.info(f"Turning {self.name} on GPIO pin {self.gpio_pin} ON.")
        self.state_start_time = time()
        self._load.on()

    def off(self) -> None:
        """Switches the load on (set the pin high."""
        LOG.info(f"Turning {self.name} on GPIO pin {self.gpio_pin} OFF.")
        self.state_start_time = time()
        self._load.off()

    @property
    def current_power(self) -> int:
        """
        Return how much power the load draws in Watt.
        For now it returns the max_power, until a current sensing mechanism is in place.
        """
        return self.max_power

    @property
    def switch_on_power(self) -> float:
        """Power in watt to be injected before the load can be switched on."""
        return self.max_power * self.switch_threshold / 100

    @property
    def switch_off_power(self) -> float:
        """Power to be consumed before the load is swicthed off."""
        return self.max_power * (100 - self.switch_threshold) / 100

    @property
    def state_time(self):
        """
        Count how many seconds we are in a stable state (on of off).
        Return -1 if the state is not defined yet.
        """
        if self.state_start_time is None:
            return -1

        return int(time() - self.state_start_time)


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
        if threshold not in THRESHOLD_NAMES:
            raise ValueError(f"Threshold not in {THRESHOLD_NAMES}")

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
    """Manages a connected load."""

    def __init__(self) -> None:
        # Setup the load(s)
        # pin GPIO24
        self.load = Load(
            pin=24, name="car charger", max_power=230 * 6, switch_threshold=75
        )
        self.timer = Timer()

    def process(self, data: Dict) -> None:
        """
        Process the data coming from the digital meter, and switch the load if needed.
        """
        actual_injected = data.get("actual_total_injection", 0)
        actual_consumed = data.get("actual_total_consumption", 0)
        LOG.debug(
            f"Load manager: Processing data: actual injected={actual_injected}W, actual consumed={actual_consumed}W."
        )

        # Start the timer if the actual power is crossing the upper threshold.
        if not self.timer.is_started and actual_injected >= self.load.switch_on_power:
            LOG.debug(
                "Loadmanager: upper threshold crossed, started the stablity timer."
            )
            self.timer.start(threshold="upper")
            return

        # Start the timer if the actual power is crossing the lower threshold.
        if not self.timer.is_started and actual_consumed >= self.load.switch_off_power:
            LOG.debug(
                "Loadmanager: lower threshold crossed, started the stablity timer."
            )
            self.timer.start(threshold="lower")
            return

        # Reset the timer if the actual power is between both thresholds, or when is is crossing the oposite threshold.
        if self.timer.is_started and (
            actual_injected < self.load.switch_on_power
            and actual_consumed == 0
            or actual_consumed < self.load.switch_off_power
            and actual_injected == 0
        ):
            self.timer.reset()
            return

        # Switch on load.
        # If the elapsed time of the stability timer is more than 5 minutes.
        if self.timer.elapsed > 300 and actual_injected > self.load.switch_on_power:
            LOG.info("Loadmanager: switching the load on.")
            self.load.on()
            self.timer.stop()
            return

        # Switch off load.
        # If the elapsed time of the stability timer is more than 5 minutes.
        if self.timer.elapsed > 300 and actual_consumed >= self.load.switch_off_power:
            LOG.info("Loadmanager: switching the load off.")
            self.load.off()
            self.timer.stop()
            return

        return


class Display:
    """
    Class to manage the oled display.
    """
    oled_witdh = 128
    oled_height = 64
    display_address = 0x3C

    def __init__(self) -> None:
        """ Initialize the display."""
        _i2c = board.I2C()
        _display_bus = displayio.I2CDisplay(_i2c, device_address=self.display_address)
        self._display = adafruit_displayio_ssd1306.SSD1306(
            _display_bus, width=self.oled_witdh, height=self.oled_height
        )
        self._splash = displayio.Group(max_size=10)
        self._display.show(self._splash)
        self._bitmap = displayio.Bitmap(width=self.oled_witdh, height=self.oled_height, value_count=1)
        _color_palette = displayio.Palette(1)
        _color_palette[0] = 0x0  # Black
        _background_sprite = displayio.TileGrid(self._bitmap, pixel_shader=_color_palette, x=0, y=0)
        self._splash.append(_background_sprite)

    def update_display(self):
        """
        Update the display with the latest info:
         - Charging current
         - Charging power
         - Duration of the current charge cycle
         - Power generated by the solar panels (if available)
        """
        # Format the way the data is printed on the LCD


class CurrentSensors:
    """
    Manages the 2 current sensors. One sensor measure the load current of the car,
    the other one measures the power coming from the solar panels.
    """

    def __init__(self) -> None:
        self.current_vvp = gpio.MCP3204(channel=0, max_voltage=2.5)
        self.current_car = gpio.MCP3204(channel=1, max_voltage=2.5)

    def vpp_current(self):
        """Return current produced by the solar panels (PVV)."""
        return 0


if __name__ == "__main__":

    d = Display()

