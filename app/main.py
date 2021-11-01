import os
import argparse
import configparser
from typing import List, Union
import logging
from logging.handlers import RotatingFileHandler
from coloredlogs import ColoredFormatter


def convert_from_human_readable(value: Union[str, int]) -> int:
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


def main() -> None:
    """
    Main entrypoint for the script.
    Parse the CLI options, load the config and setup the logging.
    """
    log = setup_log(filename="testfile.log", log_to_stdout=True)
    log.info("---start---")


if __name__ == "__main__":
    main()
