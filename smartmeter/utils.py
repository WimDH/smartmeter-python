from typing import Any, Dict, Union
import multiprocessing as mp
from datetime import datetime
from dateutil import parser as dateutil_parser
import re
import logging
from logging.handlers import RotatingFileHandler, QueueHandler
from coloredlogs import ColoredFormatter


def main_logger(
    log_queue: mp.Queue,
    filename: str,
    log_to_stdout: bool = False,
    keep: int = 2,
    size: str = "1M",
    loglevel: str = "info",
) -> logging.Logger:
    """
    Setup the logging targets.
    """
    logger = logging.getLogger("smartmeter")
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
            ColoredFormatter("%(asctime)s %(levelname)s - %(message)s")
        )
        logger.addHandler(console_handler)

    while True:
        log_record = log_queue.get()
        if log_record is None:
            logger.debug("Stopping the logging process.")
            break
        logger.handle(log_record)


def child_logger(queue, log_level="info"):
    """
    Create a logger for the child processes.
    """
    logger = logging.getLogger("smartmeter")
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.addHandler(QueueHandler(queue))

    return logger


# def get_queue_logger():
#     return logging.getLogger("queue_logger")


def autoformat(value: Union[str, int, float]) -> Union[str, int, float]:
    """Convert to str, int or float, based on the content."""
    if type(value) == str and re.match(r"^\d+$", value):
        return int(value)
    if type(value) == str and re.match(r"\d+\.\d+", value):
        return float(value)
    if type(value) == int or type(value) == float:
        return value

    return str(value)


def convert_timestamp(timestamp: str) -> str:
    """
    Convert a timestamp in the for of '211024195235S' in iso8601 format.
    YYMMDDHHMMSS[WS]
    Last letter can be a S (summer) or a W (winter).
    """
    if timestamp == "":
        raise ValueError("Timestamp cannot be empty.")

    tz_map: Dict = {"S": "02:00", "W": "01:00"}
    year: str = "20" + timestamp[0:2]
    month: str = timestamp[2:4]
    day: str = timestamp[4:6]
    hour: str = timestamp[6:8]
    minute: str = timestamp[8:10]
    second: str = timestamp[10:12]
    tz: str = tz_map[timestamp[-1]]

    iso8601_timestamp = f"{year}-{month}-{day}T{hour}:{minute}:{second}+{tz}"

    # LOG.debug("Converted timestamp from {} to {}".format(timestamp, iso8601_timestamp))

    return iso8601_timestamp


def calculate_timestamp_drift(ts_type: str, iso_8601_timestamp: str) -> int:
    """
    Calculates the drift between the system time and the telegram timestamp.
    Log a warning message when the drift is more than one minute. (Disabled)
    """
    local_timestamp = datetime.now().astimezone()
    telegram_timestamp = dateutil_parser.parse(iso_8601_timestamp)
    delta_seconds = int((local_timestamp - telegram_timestamp).total_seconds())
    # delta_human_readable = "{:0>8}".format(str(timedelta(seconds=delta_seconds)))
    #
    # log_msg = f"Timestamp for {ts_type} drift is: {delta_human_readable}."
    #
    # if delta_seconds < 60:
    #     LOG.debug(log_msg)
    # else:
    #     LOG.warning(log_msg)

    return delta_seconds


def convert_from_human_readable(value: Union[str, int]) -> int:
    """
    Converts human readable formats to an integer.
    Supports only filesizes for the moment (1k = 1024 bytes).
    k = kilo
    M = mega
    G = giga
    """
    power = {"k": 1, "M": 2, "G": 3}

    if type(value) == int or (type(value) == str and value.isnumeric()):
        return int(value)
    elif type(value) == str and value[-1] in ["k", "M", "G"]:
        return int(value[:-1]) * (1024 ** power.get(value[-1], 0))
    else:
        raise ValueError(f"'{value}' is an unknown value.")


class Borg:
    """A Borg Singleton."""

    _shared_state: Dict = {}

    def __init__(self) -> None:
        self.__dict__ = self._shared_state


class Status(Borg):
    """An object to cache the latest meter data and various states and measured values."""

    def __init__(self, data: Any) -> None:
        Borg.__init__(self)
        self.data = data
