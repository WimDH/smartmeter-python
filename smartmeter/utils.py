from typing import Dict, Union
from datetime import datetime, timedelta
from dateutil import parser as dateutil_parser
import re
from logging import getLogger

LOG = getLogger(".")


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

    LOG.debug("Converted timestamp from {} to {}".format(timestamp, iso8601_timestamp))

    return iso8601_timestamp


def calculate_timestamp_drift(ts_type: str, iso_8601_timestamp: str) -> int:
    """
    Calculates the drift between the system time and the telegram timestamp.
    Log a warning message when the drift is more than one minute.
    """
    local_timestamp = datetime.now().astimezone()
    telegram_timestamp = dateutil_parser.parse(iso_8601_timestamp)
    delta_seconds = int((local_timestamp - telegram_timestamp).total_seconds())
    delta_human_readable = "{:0>8}".format(str(timedelta(seconds=delta_seconds)))

    log_msg = f"Timestamp for {ts_type} drift is: {delta_human_readable}."

    if delta_seconds < 60:
        LOG.debug(log_msg)
    else:
        LOG.warning(log_msg)

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
