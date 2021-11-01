import os
import sys
import pathlib
import pytest
import re
from typing import List

sys.path.append(
    os.path.abspath(os.path.join(pathlib.Path(__file__).parent.resolve(), ".."))
)

from app.digimeter import parse, autoformat, check_msg

ROOT_DIR = os.path.abspath(os.path.join(pathlib.Path(__file__).parent.resolve(), ".."))


@pytest.fixture
def one_msg() -> List:
    """Load a single message from the testfile."""
    with open("tests/testdata/meter_output.txt", "r") as fh:
        return fh.read()


def test_parse_message(one_msg):
    """Test parsing of one message coming from the meter."""
    msg = parse(one_msg)

    assert msg["total_consumption_day"] == 4248.198
    assert msg["total_consumption_night"] == 6615.642
    assert msg["total_injection_day"] == 2278.958
    assert msg["total_injection_night"] == 908.264
    assert msg["actual_tariff"] == 2
    assert msg["actual_total_consumption"] == 0.507
    assert msg["actual_total_injection"] == 0
    assert msg["actual_l1_consumption"] == 0.245
    assert msg["actual_l2_consumption"] == 0
    assert msg["actual_l3_consumption"] == 0.261
    assert msg["actual_l1_injection"] == 0
    assert msg["actual_l2_injection"] == 0
    assert msg["actual_l3_injection"] == 0
    assert msg["l1_voltage"] == 227.1
    assert msg["l2_voltage"] == 0
    assert msg["l3_voltage"] == 226.7
    assert msg["l1_current"] == 1.53
    assert msg["l2_current"] == 1.94
    assert msg["l3_current"] == 1.65
    assert msg["total_gas_consumption"] == 3775.342
    assert msg["gas_last_timestamp"] == 211024195005


def test_autoformat():
    """Test autoformatting of parameters in the parsed msg."""
    assert type(autoformat("test")) == str
    assert type(autoformat("1234")) == int
    assert type(autoformat("12.34")) == float


def test_check_msg(one_msg):
    """
    Test the crc check for a message.
    We must change the EOL character from \n to \r to make the CRC check work.
    msg is ASCII encoded.
    Return True if the calculated CRC matches the provided CRC.
    """
    msg = re.sub(b"\n", b"\r\n", one_msg.encode("ascii"))
    assert check_msg(msg) is True
