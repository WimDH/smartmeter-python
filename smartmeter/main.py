import asyncio
import sys
import os
import argparse
import configparser
from typing import List, Dict, Optional
import logging
from logging.handlers import RotatingFileHandler
from coloredlogs import ColoredFormatter
import multiprocessing as mp
from smartmeter.digimeter import read_serial, fake_serial
from smartmeter.influx import DbInflux
from smartmeter.aux import Display, LoadManager, Buttons
from smartmeter.utils import convert_from_human_readable


try:
    import gpiozero as gpio
except ImportError:
    pass


def not_on_a_pi():
    """Report if we are not a Raspberry PI."""
    try:
        if os.environ["GPIOZERO_PIN_FACTORY"] == "mock":
            return True
    except KeyError:
        pass

    return False


def parse_cli(cli_args: List) -> argparse.Namespace:
    """Process the CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Read and process data from the digital enery meter."
    )
    parser.add_argument("-c", "--config", dest="configfile", help="The config file.")
    parser.add_argument(
        "-f",
        "--fake",
        dest="fake_serial",
        help="Instead of reading the data from the serial port, you can specify a file with pre recorded data.",
    )
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


def worker(
    log: logging.Logger,
    q: mp.Queue,
    influx_db_cfg: Optional[Dict],
    load_cfg: Optional[Dict],
) -> None:
    """
    Main worker to run in a separate process.
    """
    db = None
    load = None

    if influx_db_cfg:
        db = DbInflux(
            url=influx_db_cfg.get("url"),
            token=influx_db_cfg.get("token"),
            org=influx_db_cfg.get("org"),
            bucket=influx_db_cfg.get("bucket"),
            timeout=influx_db_cfg.get("timeout", 10000),
            verify_ssl=influx_db_cfg.get("verify_ssl", True),
        )

    if load_cfg:
        load = LoadManager(
            max_consume=load_cfg.getint("max_consume"),
            max_inject=load_cfg.getint("max_inject"),
            lower_threshold=load_cfg.getint("lower_treshold"),
            upper_treshold=load_cfg.getint("upper_treshold"),
        )

    loop = asyncio.get_event_loop()
    asyncio.ensure_future(queue_worker(log, q, db, load))
    if not not_on_a_pi():
        # This only makes sense if we have the hardware connected.
        asyncio.ensure_future(display_worker(log))

    loop.run_forever()


async def queue_worker(
    log: logging.Logger, q: mp.Queue, db: DbInflux, load: LoadManager
) -> None:
    """
    This worker reads from the queue, controls the load and sends the datapoints to an InfluxDB.
    # TODO: Update status LED.
    """

    while True:
        try:
            if not q.empty():
                data = q.get()

                log.debug("Got data from the queue: {}".format(data))
                if db:
                    log.debug("Writing data to Influx at {}.".format(db.url))
                    await db.write(data)

                log.debug("See if we have to switch the connected load.")
                load.process(data)

            else:
                await asyncio.sleep(0.1)

        except Exception:
            log.exception("Uncaught exception in queue worker!")
            await asyncio.sleep(0.1)


async def display_worker(log: logging.Logger) -> None:
    """
    Displaying data what the inof button is pressed.
    """
    buttons = Buttons()
    display = Display()
    info_activated = False

    while True:
        try:
            if buttons.info_button.is_pressed and not info_activated:
                info_activated = True
                log.debug("Info button is pressed.")
                await display.cycle()
                info_activated = False

        except Exception:
            log.exception("Uncaught exception in display worker!")
            info_activated = False

        await asyncio.sleep(0.1)


def main() -> None:
    """
    Main entrypoint for the script.
    Parse the CLI options, load the config and setup the logging.
    """
    args = parse_cli(sys.argv[1:])
    config = load_config(args.configfile)
    log = setup_log(
        filename=config.get(section="logging", option="logfile"),
        log_to_stdout=config.getboolean(section="logging", option="log_to_stdout"),
        keep=config.getint(section="logging", option="keep"),
        size=config.get(section="logging", option="size"),
        loglevel=config.get(section="logging", option="loglevel"),
    )
    log.info("---start---")

    if not_on_a_pi():
        log.critical(
            "It seems we are not running on a Raspberry PI! Some data is mocked!"
        )

    log.info("Board info: {}".format(str(gpio.pi_info())))

    if "influx" in config.sections() and config.getboolean(
        section="influx", option="enabled"
    ):
        influx_cfg = config["influx"]
        log.debug("InfluxDB is configured at {}".format(influx_cfg["url"]))
    else:
        influx_cfg = None
        log.info("InfluxDB is disabled or not configured!")

    if "load" in config.sections() and config.getboolean(
        section="load", option="enabled"
    ):
        load_cfg = config["load"]
        log.debug("Load management is enabled.")
    else:
        load_cfg = None
        log.info("Load management is disabled or not configured!")

    io_msg_q: mp.Queue = mp.Queue()

    if not args.fake_serial:
        log.info(
            "Starting serial port reader on port '{}'.".format(config["serial"]["port"])
        )
        serial_process = mp.Process(
            target=read_serial,
            args=(
                io_msg_q,
                config.get(section="serial", option="port"),
                config.get(section="serial", option="baudrate"),
                config.getint(section="serial", option="bytesize"),
                config.get(section="serial", option="parity"),
                config.getint(section="serial", option="stopbits"),
            ),
        )
        serial_process.start()

    else:
        log.info("Faking serial port by reading data from {}.".format(args.fake_serial))
        fake_serial_process = mp.Process(
            target=fake_serial,
            args=(
                io_msg_q,
                args.fake_serial,
                False,
                True,
            ),
        )
        fake_serial_process.start()

    log.info("Starting worker.")
    dispatcher_process = mp.Process(
        target=worker, args=(log, io_msg_q, influx_cfg, load_cfg)
    )
    dispatcher_process.start()
    dispatcher_process.join()


if __name__ == "__main__":
    main()
