import os
import json
from smartmeter.csv_writer import CSVWriter, WIP_PREFIX
import asyncio
from time import sleep


def load_json_datapoints() -> json:
    """
    Load the datapoints from a JSON file.
    Remove local_timestamp, as it is not used in the CSV file.
    Use the first item in the list, remove the local timestamp and
    duplicate it 4 times.
    """
    data = None
    with open(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "testdata/datapoints.json"
        )
    ) as jf:
        data = json.load(jf)

    row = data[0]
    del row["local_timestamp"]
    data = [row for r in range(5)]

    return data


def test_write_to_file() -> None:
    """
    Test if we can create and write to a file.
    A temp file is created with a WIP prefix and renamed afterwards.
    """
    data = load_json_datapoints()

    writer = CSVWriter(
        prefix="smartmeter_testfile",
        path="/tmp",
        write_header=True,
        max_lines=5,
        write_every=2,
    )

    for row in data:
        writer.write(row)

    writer.close(flush=True)

    filename = os.path.join(
        writer.path, os.path.split(writer.filename)[1][len(WIP_PREFIX) :]
    )

    assert os.path.exists(filename)
    assert os.stat(filename).st_size == 1109


def test_rotate_on_max_lines() -> None:
    """"""
    data = load_json_datapoints()

    writer = CSVWriter(
        prefix="smartmeter_testfile", path="/tmp", write_header=True, max_lines=2
    )
    files = []
    for row in data:
        writer.write(row)
        files.append(writer.filename)

    writer.close(flush=True)

    assert len(set(files)) == 3


def test_rotate_on_max_age():
    """"""
    data = load_json_datapoints()
    data += data

    writer = CSVWriter(
        prefix="smartmeter_testfile", path="/tmp", write_header=True, max_age=3
    )
    files = []
    for row in data:
        writer.write(row)
        files.append(writer.filename)
        sleep(1)

    writer.close(flush=True)

    assert len(set(files)) == 3
