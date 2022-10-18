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


# How many measurements do we cache. Oldest ones are removed is cache is full.
MAX_DATAPOINTS_CACHE = 90000


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
    loop = asyncio.get_event_loop()
    log = logging.getLogger()

    if influx_db_cfg:
        db = DbInflux(
            url=influx_db_cfg.get("url"),
            token=influx_db_cfg.get("token"),
            org=influx_db_cfg.get("org"),
            bucket=influx_db_cfg.get("bucket"),
            timeout=influx_db_cfg.getint("timeout", 10000),
            verify_ssl=influx_db_cfg.getboolean("verify_ssl", True),
        )

    if load_cfg:
        loads = LoadManager()
        log.info("Adding the loads to the loadmanager.")
        [loads.add_load(l) for l in load_cfg]
        log.debug("Start queue worker routine.")
        asyncio.ensure_future(
            queue_worker(msg_q, db, loads, influx_db_cfg.getint("upload_interval", 0))
        )

    if not not_on_a_pi():
        # This only makes sense if we have the hardware connected.
        log.debug("Start display_worker routine.")
        asyncio.ensure_future(display_worker())

    loop.run_forever()


async def queue_worker(
    msg_queue: mp.Queue,
    db: Union[DbInflux, None],
    loads: Union[LoadManager, None],
    upload_interval: Union[int, None],
) -> None:
    """
    Read from the queue, control the load and send the datapoints to an InfluxDB.
    # TODO: Update status LED.
    """
    log = logging.getLogger()
    msg_count = 0
    msg_pointer = 0
    msg_last_time = 0
    measurement_list = []
    start_time = time.monotonic()

    while True:
        try:
            if not msg_queue.empty():
                data = msg_queue.get()
                msg_count += 1

                log.debug("Got data from the queue: {}".format(data))

                if loads:
                    # See if we have to switch the connected load.
                    status = loads.process(data)

                if db:
                    # Writing data to InfluxDB. Allow to upload data in bulk.
                    if len(measurement_list) >= MAX_DATAPOINTS_CACHE:
                        measurement_list = measurement_list[1:]

                    measurement_list.append(data)
                    if (
                        time.monotonic() > start_time + upload_interval
                    ):
                        db.write(measurement_list)
                        start_time = time.monotonic()

            else:
                await asyncio.sleep(0.1)

            if (
                int(time.monotonic()) % 60 == 0
                and (int(time.monotonic()) - msg_last_time) > 5
            ):
                log.info(
                    "The worker processed {} messages from the queue in the last minute. (delta {})".format(
                        msg_count, msg_count - msg_pointer
                    )
                )
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
    load_cfg: Union[List[configparser.SectionProxy], None] = None

    if "influx" in config.sections() and config.getboolean(
        section="influx", option="enabled"
    ):
        influx_cfg = config["influx"]
        log.debug("InfluxDB is configured at {}".format(influx_cfg["url"]))
    else:
        log.info("InfluxDB is disabled or not configured!")

    # Get all the loads from the configfile
    load_cfg = [config[s] for s in config.sections() if s.startswith("load")]

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
