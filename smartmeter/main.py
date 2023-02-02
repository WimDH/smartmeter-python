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
from smartmeter.csv_writer import CSVWriter
from smartmeter.aux import Display, LoadManager, Buttons
from smartmeter.utils import child_logger, main_logger

try:
    import gpiozero as gpio
except ImportError:
    pass


def stopall_handler(signum, frame):
    """Stop all processes, swicth off the load and clear the display."""
    log = logging.getLogger()
    log.warning("Signal handler called with signal {}".format(signum))
    log.info("---Shutdown---")
    log.info(None)
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
    log_q: mp.Queue,
    msg_q: mp.Queue,
    influx_db_cfg: Optional[configparser.SectionProxy],
    csv_cfg: Optional[configparser.SectionProxy],
    load_cfg: Optional[configparser.SectionProxy],
) -> None:
    """
    Main worker to run in a separate process.
    Spawns coroutines.
    """
    db = None
    csv_writer = None
    loop = asyncio.get_event_loop()
    global log
    log = child_logger(log_q)

    if influx_db_cfg and influx_db_cfg.getboolean("enabled"):
        db = DbInflux(
            url=influx_db_cfg.get("url"),
            token=influx_db_cfg.get("token"),
            org=influx_db_cfg.get("org"),
            bucket=influx_db_cfg.get("bucket"),
            timeout=influx_db_cfg.getint("timeout", 10000),
            verify_ssl=influx_db_cfg.getboolean("verify_ssl", True),
        )

    if csv_cfg and csv_cfg.getboolean("enabled"):
        csv_writer = CSVWriter(
            prefix=influx_db_cfg.get("file_prefix", "smartmeter_"),
            path=influx_db_cfg.get("path"),
            write_header=influx_db_cfg.getboolean("write_header", True),
            write_every=influx_db_cfg.get("write_every", 30),
            max_lines=influx_db_cfg.get("max_lines"),
            max_age=influx_db_cfg.get("max_age"),
        )

    if load_cfg:
        loads = LoadManager()
        log.info("Adding the loads to the loadmanager.")
        [loads.add_load(l) for l in load_cfg]

    log.debug("Start queue worker routine.")
    asyncio.ensure_future(
            queue_reader(msg_q, db, csv_writer, loads, influx_db_cfg.getint("upload_interval", 0))
        )

    if not not_on_a_pi():
        # This only makes sense if we have the hardware connected.
        log.debug("Start display_worker routine.")
        asyncio.ensure_future(display_worker())

    loop.run_forever()


async def queue_reader(
    msg_queue: mp.Queue,
    db: Union[DbInflux, None],
    csv_writer: Union[CSVWriter, None],
    loads: Union[LoadManager, None],
    upload_interval: Union[int, None],
) -> None:
    """
    Read from the queue, control the load and send the datapoints to an InfluxDB.
    # TODO: Update status LED.
    """
    log.debug("Starting queue reader.")
    msg_count = 0

    while True:
        try:
            if not msg_queue.empty():
                data = msg_queue.get()
                msg_count += 1

                log.debug("Got data from the queue: {}".format(data))

                if loads:
                    # See if we have to switch the connected load.
                    loads.process(data)

                if db:
                    # InfluxDB
                    log.debug("Writing data to InfluxDB.")
                    await db.write(data, upload_interval)

                if csv_writer:
                    log.debug("Writing data to CSV files.")
                    # CSV writer
                    csv_writer.write(data)

            else:
                await asyncio.sleep(0.1)

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
            config.get(section="logging", option="loglevel"),
        ),
    )
    log_process.start()

    log = child_logger(log_queue)
    log.info("---Start---")

    if not_on_a_pi():
        log.warning(
            "It seems we are not running on a Raspberry PI! Some data is mocked!"
        )

    log.debug("Board info: {}".format(str(gpio.pi_info())))

    influx_cfg: Union[configparser.SectionProxy, None] = None
    csv_cfg: Union[configparser.SectionProxy, None] = None
    load_cfg: Union[List[configparser.SectionProxy], None] = None

    if "influx" in config.sections() and config.getboolean(
        section="influx", option="enabled"
    ):
        influx_cfg = config["influx"]
        log.debug("InfluxDB is configured at {}".format(influx_cfg["url"]))
    else:
        log.info("InfluxDB is disabled or not configured!")

    if "csv" in config.sections() and config.getboolean(
        section="csv", option="enabled"
    ):
        csv_cfg = config["csv"]
        log.debug("CSV writer is configured to write to {}".format(csv_cfg["file_path"]))
    else:
        log.info("CSV writer is disabled or not configured!")

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
                log_queue,
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
                log_queue,
                io_msg_q,
                args.fake_serial,
                True,
            ),
        )
        fake_serial_process.start()

    log.info("Starting dispatcher process.")
    dispatcher_process = mp.Process(
        target=main_worker, args=(log_queue, io_msg_q, influx_cfg, csv_cfg, load_cfg)
    )
    dispatcher_process.start()
    dispatcher_process.join()
    log_process.join()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, stopall_handler)
    signal.signal(signal.SIGTERM, stopall_handler)
    signal.signal(signal.SIGHUP, stopall_handler)

    main()
