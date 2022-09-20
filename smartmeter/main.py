import signal
import asyncio
import sys
import os
import argparse
import configparser
from typing import List, Optional, Union
import logging
import multiprocessing as mp
from smartmeter.digimeter import read_serial, fake_serial
from smartmeter.influx import DbInflux
from smartmeter.aux import Display, LoadManager, Buttons
from smartmeter.utils import child_logger, main_logger
import time

try:
    import gpiozero as gpio
except ImportError:
    pass


def stopall_handler(signum, frame):
    """Stops all processes and swicthes off the load and clears the display."""
    log = logging.getLogger()
    log.warning("Signal handler called with signal {}".format(signum))
    log.info("---Shutdown---")
    sys.exit(0)


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


def main_worker(
    loglevel: str,
    log_q: mp.Queue,
    msg_q: mp.Queue,
    influx_db_cfg: Optional[configparser.SectionProxy],
    load_cfg: Optional[configparser.SectionProxy],
) -> None:
    """
    Main worker to run in a separate process.
    Spawns coroutines.
    """
    db = None
    load = None
    loop = asyncio.get_event_loop()
    log = logging.getLogger()

    if influx_db_cfg:
        db = DbInflux(
            host=influx_db_cfg.get("host"),
            username=influx_db_cfg.get("username"),
            password=influx_db_cfg.get("password"),
            database=influx_db_cfg.get("database"),
            timeout=influx_db_cfg.getint("timeout", 10000),
        )

    if load_cfg:
        load = LoadManager(
            max_consume=load_cfg.getint("max_consume"),
            max_inject=load_cfg.getint("max_inject"),
            consume_time=load_cfg.getint("consume_time"),
            inject_time=load_cfg.getint("inject_time"),
        )
        log.debug("Start queue_worker routine")
        asyncio.ensure_future(queue_worker(msg_q, db, load))

    if not not_on_a_pi():
        # This only makes sense if we have the hardware connected.
        log.debug("Start display_worker routine")
        asyncio.ensure_future(display_worker())

    loop.run_forever()


async def queue_worker(
    msg_queue: mp.Queue,
    db: Union[DbInflux, None],
    load: Union[LoadManager, None],
) -> None:
    """
    This worker reads from the queue, controls the load and sends the datapoints to an InfluxDB.
    # TODO: Update status LED.
    """
    log = logging.getLogger()
    msg_count = 0
    msg_pointer = 0
    msg_last_time = 0

    while True:
        try:
            if not msg_queue.empty():
                data = msg_queue.get()
                msg_count += 1

                log.debug("Got data from the queue: {}".format(data))

                if load:
                    # See if we have to switch the connected load.
                    load.process(data, db)
                    data.update({'load_status': load.load.is_on})

                if db:
                    # Writing data to InfluxDB
                    db.write(data)

            else:
                await asyncio.sleep(0.1)

            if (
                int(time.monotonic()) % 60 == 0 and
                (int(time.monotonic()) - msg_last_time) > 5
            ):
                log.info("The worker processed {} messages from the queue in the last minute. (delta {})".format(msg_count, msg_count - msg_pointer))  # noqa E501
                msg_pointer = msg_count
                msg_last_time = int(time.monotonic())

        except Exception:
            log.exception("Uncaught exception in queue worker!")
            await asyncio.sleep(0.1)


async def display_worker() -> None:
    """
    Displaying data when the info button is pressed.
    """
    buttons = Buttons()
    display = Display()
    info_activated = False
    log = logging.getLogger()

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
    log_queue = mp.Queue()
    log_level = config.get(section="logging", option="loglevel")
    log_process = mp.Process(
        target=main_logger,
        args=(
            log_queue,
            os.path.join(
                config.get(section="logging", option="logpath"), "smartmeter.log"
            ),
            config.getboolean(section="logging", option="log_to_stdout"),
            config.getint(section="logging", option="keep"),
            config.get(section="logging", option="size"),
            log_level,
        ),
    )
    log_process.start()

    log = child_logger(log_level, log_queue)
    log.info("---Start---")

    if not_on_a_pi():
        log.warning(
            "It seems we are not running on a Raspberry PI! Some data is mocked!"
        )

    log.debug("Board info: {}".format(str(gpio.pi_info())))

    influx_cfg: Union[configparser.SectionProxy, None] = None
    load_cfg: Union[configparser.SectionProxy, None] = None

    if "influx" in config.sections() and config.getboolean(
        section="influx", option="enabled"
    ):
        influx_cfg = config["influx"]
        log.debug("InfluxDB is configured at {}".format(influx_cfg["host"]))
    else:
        log.info("InfluxDB is disabled or not configured!")

    if "load" in config.sections() and config.getboolean(
        section="load", option="enabled"
    ):
        load_cfg = config["load"]
        log.debug("Load management is enabled.")
    else:
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
                True,
            ),
        )
        fake_serial_process.start()

    log.info("Starting worker.")
    dispatcher_process = mp.Process(
        target=main_worker, args=(log_level, log_queue, io_msg_q, influx_cfg, load_cfg)
    )
    dispatcher_process.start()
    dispatcher_process.join()
    log_process.join()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, stopall_handler)
    signal.signal(signal.SIGTERM, stopall_handler)
    signal.signal(signal.SIGHUP, stopall_handler)

    main()
