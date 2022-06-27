from logging import getLogger
from typing import Union, Optional, Dict
from time import time, sleep
from PIL import Image, ImageDraw, ImageFont
import asyncio

try:
    import board
    import adafruit_ssd1306

except (ImportError, NotImplementedError):
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

    switch_threshold is expressed in percent and represents the amount of power that has to come from the solar panels.
    """

    def __init__(self, pin: int, name: str, max_power: int) -> None:
        self._load = gpio.DigitalOutputDevice(
            pin=pin, initial_value=False
        )  # See pin numbering
        self.gpio_pin: int = pin
        self.name: str = name
        self.max_power: float = max_power
        self.state_start_time: Optional[float] = None

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
    def current_power(self) -> float:
        """
        Return how much power the load draws in Watt.
        For now it returns the max_power, until a current sensing mechanism is in place.
        """
        return self.max_power

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
    Represents a timer that count how long the actual power crossed it's threshold (in seconds).
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

    def __init__(
        self,
        max_consume: int,
        max_inject: int,
    ) -> None:
        # Setup the load
        # pin GPIO24
        self.max_consume = max_consume
        self.max_inject = max_inject
        self.load = Load(pin=24, name="car charger", max_power=230 * 10)
        self.timer = Timer()

    def process(self, data: Dict) -> None:
        """
        Process the data coming from the digital meter, and switch the load if needed.
        """
        actual_injected = data.get("actual_total_injection", 0) * 1000
        actual_consumed = data.get("actual_total_consumption", 0) * 1000
        LOG.debug(
            f"Load manager: Processing data: actual injected={actual_injected}W, actual consumed={actual_consumed}W."
        )

        # # Start the timer if the actual power is crossing max power to inject.
        # if not self.timer.is_started and actual_injected >= self.max_inject:
        #     LOG.debug(
        #         "Loadmanager: upper threshold crossed, started the stablity timer."
        #     )
        #     self.timer.start(threshold="upper")

        # # Start the timer if the actual power is crossing max power to consume.
        # if not self.timer.is_started and actual_consumed >= self.max_consume:
        #     LOG.debug(
        #         "Loadmanager: lower threshold crossed, started the stablity timer."
        #     )
        #     self.timer.start(threshold="lower")

        # Switch on load.
        if actual_injected > self.max_inject:
            LOG.info("Loadmanager: switching the load ON.")
            self.load.on()
            self.timer.stop()

        # Switch off load.
        if actual_consumed >= self.max_consume:
            LOG.info("Loadmanager: switching the load OFF.")
            self.load.off()
            self.timer.stop()


class Display:
    """
    Class to manage the oled display.
    """

    oled_witdh = 128
    oled_height = 64
    display_address = 0x3C

    def __init__(self) -> None:
        """Initialize the display."""
        _i2c = board.I2C()
        self._display = adafruit_ssd1306.SSD1306_I2C(
            width=self.oled_witdh,
            height=self.oled_height,
            i2c=_i2c,
            addr=self.display_address,
        )

    def update_display(self, text: str = "") -> None:
        """
        Update the display with the given text.
        """
        image = Image.new("1", (self.oled_witdh, self.oled_height))
        draw = ImageDraw.Draw(image)
        draw.multiline_text((2, 2), text, font=ImageFont.load_default(), fill=255)
        self._display.image(image)
        self._display.show()

    def display_on(self) -> None:
        self._display.poweron()
        self.display_is_on = True

    def display_off(self) -> None:
        self._display.poweroff()
        self.display_is_on = False

    async def cycle(
        self,
        wait: int = 1,
        nbr: int = 1,
        charging_current: float = 0,
        charging_power: float = 0,
        generated_current: float = 0,
        generated_power: float = 0,
        charging_cycle: int = 0,
    ) -> None:
        """
        Cycle through all values to display, wait x seconds, and run the loop y times.
        wait: nbr of seconds to wait between each value
        nbr: how many time to run the loop
        display is turned off at the end of the last cycle
        """
        cnt = 0
        text = [
            f"Charging current:\n{charging_current}A",
            f"Charging power:\n{charging_power}W",
            f"Charging cycle:\n{charging_cycle}",
            f"Generated current:\n{generated_current}A",
            f"Generated power:\n{generated_power}W",
        ]

        self.display_on()

        while cnt < nbr:
            for t in text:
                self.update_display(text=t)
                await asyncio.sleep(wait)
            cnt += 1

        self.display_off()


class CurrentSensors:
    """
    Manages the 2 current sensors. One sensor measure the load current of the car,
    the other one measures the power coming from the solar panels.
    """

    def __init__(self) -> None:
        self.current_vvp = gpio.MCP3204(channel=0, max_voltage=2.5)
        self.current_car = gpio.MCP3204(channel=1, max_voltage=2.5)

    def vpp_current(self) -> int:
        """Return current produced by the solar panels (PVV)."""
        return 0

    def load_current(self) -> int:
        """Return the current used by the load."""
        return 0


class Buttons:
    """
    Implements the buttons Info and Restart.
    """

    debounce_time = 0.5  # Seconds

    def __init__(self) -> None:
        # GPIO17
        self.info_button = gpio.Button(
            pin=17, pull_up=True, bounce_time=self.debounce_time
        )
        # GPIO27
        self.restart_button = gpio.Button(
            pin=27, pull_up=True, bounce_time=self.debounce_time
        )


class StatusLed:
    """
    Maybe a class is a bit overkill here, but anyways...
    This toggles the status led on or of. Or it returns it's current status.
    """

    def __init__(self) -> None:
        # GPIO22
        self.led = gpio.LED(pin=22)

    def on(self):
        self.led.on()

    def off(self):
        self.led.off()

    def test(self):
        """Switch the LED on for 1 second."""
        self.led.on()
        sleep(1)
        self.led.off()

    @property
    def status(self):
        return self.led.is_active()
