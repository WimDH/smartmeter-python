from crccheck.crc import Crc16Lha
import serial
import re


FIELDS = [
    # Fieldname, dictionary key, startpos, endpos
    ("1-0:1.8.1", "total_consumption_day", 10, 20),
    ("1-0:1.8.2", "total_consumption_night", 10, 20),
    ("1-0:2.8.1", "total_injection_day", 10, 20),
    ("1-0:2.8.2", "total_injection_night", 10, 20),
    ("0-0:96.14.0", "actual_tariff", 12, 16),
    ("1-0:1.7.0", "actual_total_consumption", 10, 16),
    ("1-0:2.7.0", "actual_total_injection", 10, 16),
    ("1-0:21.7.0", "actual_l1_consumption", 11, 17),
    ("1-0:41.7.0", "actual_l2_consumption", 11, 17),
    ("1-0:61.7.0", "actual_l3_consumption", 11, 17),
    ("1-0:22.7.0", "actual_l1_injection", 11, 17),
    ("1-0:42.7.0", "actual_l2_injection", 11, 17),
    ("1-0:62.7.0", "actual_l3_injection", 11, 17),
    ("1-0:32.7.0", "l1_voltage", 11, 16),
    ("1-0:52.7.0", "l2_voltage", 11, 16),
    ("1-0:72.7.0", "l3_voltage", 11, 16),
    ("1-0:31.7.0", "l1_current", 11, 17),
    ("1-0:51.7.0", "l2_current", 11, 17),
    ("1-0:71.7.0", "l3_current", 11, 17),
    ("0-1:24.2.3", "total_gas_consumption", 26, 35),
    ("0-1:24.2.3", "gas_last_timestamp", 11, 23),
]


def autoformat(value):
    """Convert to str, int or float, based on the content."""
    if re.match(r"^\d+$", value):
        return int(value)
    if re.match(r"\d+\.\d+", value):
        return float(value)

    return str(value)


def parse(raw_msg):
    """Parse the raw message."""
    msg = {}

    for line in raw_msg.strip().splitlines():
        for (code, key, start, end) in FIELDS:
            if line.startswith(code):
                msg[key] = autoformat(line[start:end])

    return msg


def check_msg(raw_msg: str) -> bool:
    """
    Check if the message is valid.
    The provided CRC is
    """
    # Find the end of message character '!'
    pos = raw_msg.find(b"!")
    data = raw_msg[: pos + 1]
    provided_crc = hex(int(raw_msg[pos + 1 :].strip(), 16))
    calculated_crc = hex(Crc16Lha.calc(data))
    return calculated_crc == provided_crc


def read_serial() -> str:
    """
    Read from the serial port until a complete message is detected.
    When the message is complete, add ir to the msg Queue as a sting.
    """
    line: bytes

    try:
        # Todo: move serial port setting to somewhere else.
        serial_port = serial.Serial("/dev/serial0", 115200)

        while True:
            # Read data from port
            line = serial_port.readline()
            print(line)

    except Exception:
        pass
