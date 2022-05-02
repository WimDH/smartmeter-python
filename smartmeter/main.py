import sys
import os
import argparse
import configparser
from typing import List, Dict, Optional
import logging
from logging.handlers import RotatingFileHandler
from coloredlogs import ColoredFormatter
import multiprocessing as mp
from smartmeter.digimeter import read_serial

# from smartmeter.influx import DbInflux
from smartmeter.aux import Display, LoadManager, StatusLed
from smartmeter.utils import convert_from_human_readable
from time import sleep

# import asyncio


try:
    import gpiozero as gpio
except ImportError:
    pass


def parse_cli(cli_args: List) -> argparse.Namespace:
    """Process the CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Read and process data from the digital enery meter."
    )
    parser.add_argument("-c", "--config", dest="configfile")
    parser.add_argument("-T", "--test", action="store_true", dest="run_test")

    return parser.parse_args(cli_args)


def load_config(configfile: str) -> configparser.ConfigParser:
    """
    Load the configfile and return the parsed content.
    """
    if os.path.exists(configfile):
        config = configparser.ConfigParser()
        config.read(configfile)

        return config

    else:
        raise FileNotFoundError(f"File '{configfile}'' not found!")


def setup_log(
    filename: str,
    log_to_stdout: bool = False,
    keep: int = 2,
    size: str = "1M",
    loglevel: str = "info",
) -> logging.Logger:
    """
    Setup logging.
    """
    logger = logging.getLogger(".")
    logger.setLevel(getattr(logging, loglevel.upper()))

    # Log to a file.
    file_handler = RotatingFileHandler(
        filename=filename, maxBytes=convert_from_human_readable(size), backupCount=keep
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s - %(message)s")
    )
    logger.addHandler(file_handler)

    # Log to stdout.
    if log_to_stdout:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            ColoredFormatter("%(asctime)s %(process)d %(levelname)s - %(message)s")
        )
        logger.addHandler(console_handler)

    return logger


def worker(log: logging.Logger, q: mp.Queue, influx_db_cfg: Optional[Dict]) -> None:
    """
    This worker function sends the messages to an InfluxDB (if configured)
    and controls the relay and other I/O.
    """
    if influx_db_cfg:
        pass

    while True:
        if not q.empty():
            data = q.get()
            log.debug("Got a message for the queue: {}".format(data))
            # TODO: write to influxdb if configured.
        else:
            sleep(0.1)


def run_tests():
    """
    Run hardware tests, mostly stuff from aux.py
    return 0 is all tests are successful
    """
    # Testing the oled display.
    display = Display()
    display.update_display(text="This is a\ntest message.")

    # Tesing the status led.
    status = StatusLed()
    status.test()

    # Test the load.
    load = LoadManager()
    load.test_load()

    # Test the Buttons
    display.update_display("Press the Info and\nRestart buttons\n within 10 seconds.")

    display.display_off()
    return 0


def main() -> None:
    """
    Main entrypoint for the script.
    Parse the CLI options, load the config and setup the logging.
    """
    args = parse_cli(sys.argv[1:])
    config = load_config(args.configfile)
    log = setup_log(
        filename=config["logging"]["logfile"],
        log_to_stdout=config.getboolean("logging", "log_to_stdout"),
        keep=int(config["logging"]["keep"]),
        size=config["logging"]["size"],
        loglevel=config["logging"]["loglevel"],
    )
    log.info("---start---")

    try:
        log.info("Board info: {}".format(str(gpio.pi_info())))
    except ModuleNotFoundError:
        log.info("Board info not available.")

    if args.run_test is True:
        # Run Hardware tests
        result = run_tests()
        log.debug("Running hardware tests.")
        log.info("---done---")
        sys.exit(result)

    if config.get("influx") and config["influx"].get("enabled", True):
        influx_cfg = config.get("influx")
    else:
        influx_cfg = None
        log.info("InfluxDB is disabled!")

    msg_q: mp.Queue = mp.Queue()

    log.info(
        "Starting serial port reader on port '{}'.".format(config["serial"]["port"])
    )
    serial_process = mp.Process(
        target=read_serial,
        args=(
            msg_q,
            config["serial"]["port"],
            int(config["serial"]["baudrate"]),
            int(config["serial"]["bytesize"]),
            config["serial"]["parity"],
            int(config["serial"]["stopbits"]),
        ),
    )
    serial_process.start()

    log.info("Starting worker.")
    dispatcher_process = mp.Process(target=worker, args=(log, msg_q, influx_cfg))
    dispatcher_process.start()


if __name__ == "__main__":
    main()
