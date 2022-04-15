import sys
import os
import argparse
import configparser
from typing import List
import logging
from logging.handlers import RotatingFileHandler
from coloredlogs import ColoredFormatter
import multiprocessing as mp
from influxdb.client import InfluxDBClient
from smartmeter.digimeter import read_serial
from smartmeter.influx import DbInflux
from smartmeter.utils import convert_from_human_readable
from time import sleep

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


def dispatcher(log: logging.Logger, q: mp.Queue, influx_db: InfluxDBClient) -> None:
    """
    Dispatcher function that sends the messages to an InfluxDB
    and controls the relay and other I/O.
    """

    influx_db.connect()

    while True:
        if not q.empty():
            data = q.get()
            log.debug("Got a message for the queue: {}".format(data))
            influx_db.write(data)
        else:
            sleep(0.1)


def main() -> None:
    """
    Main entrypoint for the script.
    Parse the CLI options, load the config and setup the logging.
    """
    db = None
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

    if config["influx"]["enabled"] is True:

        log.info(
            "Setup connection for InfluxDB for database '{}' on host '{}'.".format(
                config["influx"]["database"], config["influx"]["hostname"]
            )
        )
        db = DbInflux(
            host=config["influx"]["hostname"],
            port=int(config["influx"]["port"]),
            ssl=config.getboolean("influx", "ssl"),
            verify_ssl=config.getboolean("influx", "verify_ssl"),
            database=config["influx"]["database"],
            username=config["influx"]["username"],
            password=config["influx"]["password"],
        )

    else:
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

    log.info("Starting dispatcher.")
    dispatcher_process = mp.Process(target=dispatcher, args=(log, msg_q, db))
    dispatcher_process.start()


if __name__ == "__main__":
    main()
