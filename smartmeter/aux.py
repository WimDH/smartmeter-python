import configparser
import logging
from typing import Union, Optional, Dict
from time import time
from xmlrpc.client import Boolean
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

LOG = logging.getLogger()
TIMER_TYPES = ["consume", "inject"]
LOAD_PIN = 24


class Load:
    """
    Defines a load.
    For Pin numbering: https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering

    switch_threshold is expressed in percent and represents the amount of power that has to come from the solar panels.
    """

    def __init__(
        self,
        name: str,
        max_power: int,
        switch_on: int,
        switch_off: int,
        hold_timer: int,
        address: Optional[str] = None,
    ) -> None:
        if not address:
            self._load = gpio.DigitalOutputDevice(
                pin=LOAD_PIN, initial_value=False
            )  # See pin numbering
            self.gpio_pin = LOAD_PIN
        else:
            self._load = address
            self.gpio_pin = None

        self.name = name
        self.max_power = max_power
        self.switch_on = switch_on
        self.switch_off = switch_off
        self.hold_timer = hold_timer
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
        self.state_start_time = time()
        self._load.on()

    def off(self) -> None:
        """Switches the load on (set the pin high."""
        self.state_start_time = time()
        self._load.off()

    @property
    def is_on(self) -> Boolean:
        """Return True if the load is switched on else False."""
        return True if self._load.value == 1 else False

    @property
    def is_off(self) -> Boolean:
        """Return True is the load is off, else True."""
        return not self.is_on

    @property
    def current_power(self) -> float:
        """
        Return how much power the load consumes in Watt.
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


class LoadManager:
    """Manages a connected load."""

    def __init__(self) -> None:
        self.load_list = []

    def add_load(self, load_config: configparser.SectionProxy) -> None:
        """
        Add a managed load.
        The default aux load (load:aux) is connected to pin GPIO24

        TODO: add other loads, the ones who connect over wifi or bluetooth.
        """
        if not load_config.getboolean("enabled", False):
            LOG.info("Load {} is not enabled.".format(load_config.name))

        LOG.info("Added load {}.".format(load_config.name))
        self.load_list.append(
            Load(
                name=load_config.name[5:],
                address=load_config.get("address", None),
                max_power=load_config.getint("max_power"),
                switch_on=load_config.getint("switch_on"),
                switch_off=load_config.getint("switch_off"),
                hold_timer=load_config.getint("hold_timer"),
            )
        )

    def process(self, data: Dict) -> Dict:
        """
        Process the data coming from the digital meter, and switch the loads if needed.
        Return the status for each load.
        TODO: define an order of switching on and off for all the loads
        """
        for load in self.load_list:
            actual_injected = data.get("actual_total_injection", 0) * 1000
            actual_consumed = data.get("actual_total_consumption", 0) * 1000

            if (
                load.is_off and
                actual_injected > load.switch_on and
                (load.state_time is not None and load.state_time > load.hold_timer)
            ):
                load.on()
                continue

            if (
                load.is_on and
                load.state_timer > load.hold_timer and
                (
                    load.switch_off < 0 and actual_injected < abs(load.switch_off) or
                    load.switch_off >= 0 and actual_consumed < abs(load.switch_off)
                )
            ):
                load.off()

        return {l.name: l.is_on for l in self.load_list}


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

    TODO: Add callibration functionality
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

    def on(self) -> None:
        self.led.on()

    def off(self) -> None:
        self.led.off()

    def blink(self, interval: Optional[int] = 1) -> None:
        """Make the status led blink."""
        self.led.blink(on_time=interval, off_time=interval)

    @property
    def status(self) -> Boolean:
        return self.led.is_active()
