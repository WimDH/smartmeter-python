import pytest
from smartmeter.main import parse_cli, load_config


@pytest.mark.parametrize(
    "cli_data, cfg_result, test_result, fake_result",
    [
        (
            ["-c", "tests/testdata/sample_config.ini"],
            "tests/testdata/sample_config.ini",
            False,
            None,
        ),
        (
            ["-c", "tests/testdata/sample_config.ini", "-f", "/home/test/blah.txt"],
            "tests/testdata/sample_config.ini",
            False,
            "/home/test/blah.txt",
        ),
    ],
)
def test_parse_cli(cli_data, cfg_result, test_result, fake_result) -> None:
    """Test the parsing of the CLI options."""
    options = parse_cli(cli_args=cli_data)

    assert options.configfile == cfg_result
    assert options.fake_serial == fake_result


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
        ("enabled", "yes"),
        ("url", '"https://127.0.0.1:8086"'),
        ("token", '"ABC123"'),
        ("org", '"your_org"'),
        ("verify_ssl", "yes"),
        ("bucket", "smartmeter"),
    ]

    assert config.items("csv") == [
        ("enabled", "no"),
        ("file_prefix", "smartmeter_data_"),
        ("file_path", "/data"),
        ("write_header", "yes"),
        ("max_lines", "100"),
        ("max_age", "300"),
    ]

    assert config.items("load:aux") == [
        ("enabled", "no"),
        ("max_power", "2300"),
        ("switch_on", "75"),
        ("switch_off", "10"),
        ("hold_timer", "10"),
    ]
