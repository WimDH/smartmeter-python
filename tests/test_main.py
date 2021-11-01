import pytest
import logging
import coloredlogs
from app.main import parse_cli, load_config, convert_from_human_readable, setup_log


@pytest.mark.parametrize(
    "in_value,out_value",
    [
        (1000, 1000),
        ("1000", 1000),
        ("10k", 10240),
        ("10M", 10485760),
        ("10G", 10737418240),
    ],
)
def test_convert_from_human_readable(in_value, out_value) -> None:
    """Test the conversion of ex. 10k to 10240."""
    assert convert_from_human_readable(in_value) == out_value


def test_convert_from_human_readable_fail() -> None:
    """Test when the conversion fails."""
    with pytest.raises(ValueError):
        assert convert_from_human_readable("10m")


def test_parse_cli() -> None:
    """Test the parsing of the CLI options."""
    options = parse_cli(cli_args=["-c", "tests/testdata/sample_config.ini"])

    assert options.configfile == "tests/testdata/sample_config.ini"


def test_load_config() -> None:
    """Test the load of the config file."""
    with pytest.raises(FileNotFoundError):
        load_config(configfile="tests/testdata/file_does_nor_exist.ini")

    config = load_config(configfile="tests/testdata/config_ok.ini")

    assert config.items("logging") == [
        ("loglevel", "debug"),
        ("logfile", "/path/to/logfile.log"),
        ("keep", "10"),
        ("size", "10M"),
        ("log_to_stdout", "no"),
    ]

    assert config.items("serial") == [
        ("port", "/dev/serial0"),
        ("speed", "115000"),
        ("bytes", "8"),
        ("parity", "N"),
        ("stopbits", "1"),
    ]

    assert config.items("influx") == [
        ("hostname", "127.0.0.1"),
        ("port", "8086"),
        ("database", "smartmeter"),
    ]


def test_setup_logging():
    """Test if we can setup the logging."""
    logger = setup_log(filename="testlog.log", size="1M", keep=2, log_to_stdout=True)

    assert isinstance(logger.handlers[0], logging.handlers.RotatingFileHandler)
    assert isinstance(logger.handlers[1], logging.StreamHandler)
