import os
import pathlib
import pytest
import re
from crccheck.crc import Crc16Lha
from io import BytesIO
from queue import Queue

from smartmeter.digimeter import parse, autoformat, check_msg, read_serial, serial

ROOT_DIR = os.path.abspath(os.path.join(pathlib.Path(__file__).parent.resolve(), ".."))


@pytest.fixture
def msg_stream() -> BytesIO:
    """
    Monkeypatch.
    Reads the file meter_stream, which contains multiple messages. Returns a ByteIO instance.
    Also re-calculate the CRC because we anonimized the serial numbers and ID in the testdata.
    """
    data: bytearray = bytearray()  # Main data container
    telegram: bytearray = bytearray()  # Container for one telegram
    detected_telegram_start: bool = False
    encoded_line: bytes

    with open("tests/testdata/meter_stream.txt", "r") as fh:
        for line in fh.readlines():
            # The data coming from the meter has a M$ style newline.
            encoded_line = re.sub(b"\n", b"\r\n", line.encode("ascii"))

            # Create new telegram at the start of a telegram.
            if line.startswith("/FLU"):
                telegram = bytearray()
                detected_telegram_start = True

            if detected_telegram_start and not line.startswith("!AAAA"):
                telegram += encoded_line

            # Detect end of message.
            # Re-calculate the CRC because we changed the ID and serials.
            if line.startswith("!AAAA"):
                telegram += b"!"
                calculated_crc = str(hex(Crc16Lha.calc(telegram)))[2:].upper().zfill(4)
                telegram += calculated_crc.encode("ascii") + b"\r\n"
                data += telegram
                detected_telegram_start = False

    return BytesIO(data)


@pytest.fixture
def one_msg() -> str:
    """Load a single message from the testfile."""
    with open("tests/testdata/meter_output.txt", "r") as fh:
        return fh.read()


def test_parse_message(one_msg):
    """
    Test parsing of one message coming from the meter.
    TODO: improve test
    """
    msg = parse(one_msg)

    assert isinstance(msg["local_timestamp"], str)
    assert msg["timestamp"] == "211024195235S"
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
    assert msg["gas_timestamp"] == "211024195005S"


def test_autoformat():
    """Test autoformatting of parameters in the parsed msg."""
    assert type(autoformat("test")) == str
    assert type(autoformat("1234")) == int
    assert type(autoformat("12.34")) == float


def test_read_serial(monkeypatch, msg_stream):
    """
    Test the main loop. It reads data from the serial port.
    TODO: improve test by checking content of the queue.
    """

    def mock_stream(*args, **kwargs):
        return msg_stream

    monkeypatch.setattr(serial, "Serial", mock_stream)
    q = Queue()
    read_serial(q, "com1", 2400, 8, "N", 1, _quit_after=2)

    assert q.empty() is False


def test_check_msg(one_msg):
    """
    Test the crc check for a message.
    We must change the EOL character from \n to \r to make the CRC check work.
    msg is ASCII encoded.
    Return True if the calculated CRC matches the provided CRC.
    """
    msg = re.sub(b"\n", b"\r\n", one_msg.encode("ascii"))
    assert check_msg(msg) is True


# def test_fake_serial():
#     """Test reading serial data froma file."""
#     q = Queue()
#     fake_serial(q, "tests/testdata/meter_stream.txt", wait=False)

#     assert q.empty() is False
