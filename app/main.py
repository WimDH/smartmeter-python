import sys
import os
import argparse
import configparser
import queue
from typing import List, Union
import logging
from logging.handlers import RotatingFileHandler
from coloredlogs import ColoredFormatter
import threading
from app.digimeter import read_serial


def convert_from_human_readable(value):
    """
    Converts human raedable formats to an integer.
    Supports only filesizes for the moment (1k = 1024 bytes).
    k = kilo
    M = mega
    G = giga
    """
    power = {"k": 1, "M": 2, "G": 3}

    if type(value) == int or value.isnumeric():
        return int(value)
    elif type(value) == str and value[-1] in ["k", "M", "G"]:
        return int(value[:-1]) * (1024 ** power.get(value[-1]))
    else:
        raise ValueError(f"'{value}' is an unknown value.")


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


def debug_q(q):
    while True:
        if not q.empty():
            data = q.get()
            print(data)


def main() -> None:
    """
    Main entrypoint for the script.
    Parse the CLI options, load the config and setup the logging.
    """
    args = parse_cli(sys.argv[1:])
    config = load_config(args.configfile)
    log = setup_log(
        filename=config["logging"]["logfile"],
        log_to_stdout=config["logging"]["log_to_stdout"],
        keep=config["logging"]["keep"],
        size=config["logging"]["size"],
        loglevel=config["logging"]["loglevel"]
    )
    log.info("---start---")

    msg_q = queue.Queue()

    log.info("Starting serial port reader thread.")
    serial_thread = threading.Thread(
        target=read_serial,
        args=(
            msg_q,
            config["serial"]["port"],
            int(config["serial"]["baudrate"]),
            int(config["serial"]["bytesize"]),
            config["serial"]["parity"],
            int(config["serial"]["stopbits"])
        )
    )
    serial_thread.start()

    log.info("Starting queue debuger.")
    q_thread = threading.Thread(
        target=debug_q
    )
    q_thread.start()


if __name__ == "__main__":
    main()
