# smartmeter

## Description
smartmeter is an application that reads data from the (Belgian) digital meters, allows to switch on/off loads depending on how much we draw from or inject into the grid.
The idea for this script came when the analog meters were replaced by digital ones. The latter do not count backwards, but instead count what we draw and what we inject separately.
Besides switching load, the application can export the data to an InfluxDB, or to CSV files.

## Design
Smartmeter is tested on a Raspberry Pi, but in can also run on a PC/server. During the development and initial testing, I used an old Raspberry Pi (model B rev. 2). Some of the design decisions are based upon this old model. I thought if it can run an an old pi, it must work on the newer versions as well.
![Old pi model B rev. 2](https://upload.wikimedia.org/wikipedia/commons/3/3b/Raspberry_Pi_Model_B_Rev._2.jpg)
### How it works high level
The application is running in 2 different processes (using Python's `multiprocessing` library). One is running the process to collect the data from the serial port of the meter (and some basic processing is done as well), and the other process is taking care of all the post-processing actions (like uploading the data to the InfluxDB, switching relays on and off, ...)

### What I discovered during the testing
In the beginning I was using threads (using the `threading` module), but I found out that it di not work so well. I'm not using a serial to USB cable (FTDI to RJ12), but I connected the meter using the serial port on the GPIO of the Pi, and I did not connect the CTS pin neither (maybe a bit sloppy from my side).\
While receiving data from the meter, I discovered that after a while, the delta between the timestamp in the Telegram (that's how they call a message received from the meter), and the local time on the Pi was increasing, in fact it increased with 1 second every 1 or 2 messages. After a while, the data was not real-time anymore, which made it impossible to switch load, depending on the data we received. When I swicthed to multiprocessing I did not have that problem anymore.\
I also noted that running an InfluxDb and a Grafana instance on the same Raspberry Pi isn't a good idea neither.
Despite running two separate processes, writing to the InfluxDB and reading from it (by Grafana), I still saw an increasing delay in processing the data. I didn't test it on the newer versions of the Raspberry Pis (Models 3 and 4).
Anyway, my plan is to run the Influx + Grafana in the cloud.

## Telegram lay-out

A new message starts with a forward slash `/` followed by an ID, and ending with 2 two CR/LF sequences.
The end of the message is an `!` + the 16 bit CRC.
### Fieldnames

| Obis code | Meaning | Unit | InfluxDB fieldname |
|-----------|---------|------|--------------------|
| 0-0:96.1.4 | ID |||
| 0-0:96.1.1 | Serial number of the digital meter (ASCII hex). |||
| 0-0:1.0.0  | Timestamp of the telegram || timestamp |
| 1-0:1.8.1	| Total consumption tariff 1 (day, full) | kWh | total_consumption_day |
| 1-0:1.8.2	| Total consumption tariff 2 (night, reduced) | kWh | total_consumption_night |
| 1-0:2.8.1	| Total injection tariff 1 (day, full) | kWh | total_injection_day |
| 1-0:2.8.2	| Total injection tariff 2 (night, reduced) | kWh | total_injection_night |
| 0-0:96.14.0| Actual tariff (1=full,day - 2=night,reduced) ||
| 1-0:1.7.0	| Actual consumption on all phases | kW | actual_total_consumption |
| 1-0:2.7.0	| Actual injection on all phases | kW | actual_total_injection |
| 1-0:21.7.0 | L1 actual consumption | kW | actual_l1_consumption |
| 1-0:41.7.0 | L2 actual consumption | kW | actual_l2_consumption |
| 1-0:61.7.0 | L3 actual consumption | kW | actual_l3_consumption |
| 1-0:22.7.0 | L1 actual injection | kW | actual_l1_injection |
| 1-0:42.7.0 | L2 actual injection | kW | actual_l2_injection |
| 1-0:62.7.0 | L3 actual injection | kW | actual_l3_injection |
| 1-0:32.7.0 | L1 voltage | V | l1_voltage |
| 1-0:52.7.0 | L2 voltage | V | l2_voltage |
| 1-0:72.7.0 | L3 voltage | V | l3_voltage |
| 1-0:31.7.0 | L1 current | A | l1_current |
| 1-0:51.7.0 | L2 current | A | l2_current |
| 1-0:71.7.0 | L3 current | A | l3_current |
| 0-0:96.3.10 | Position internal switch (power) ||
| 0-0:17.0.0 | Max. allowed power per phase | kW ||
| 1-0:31.4.0 | Max. allowed current per phase | A || 
| 0-0:96.13.0 | Custom messages |||
| 0-1:24.1.0 | Other devices on the bus |||
| 0-1:96.1.1 | Serial number of the gas meter (in ASCII hex) ||||
| 0-1:24.4.0 | Position switch gas meter |||
| 0-1:24.2.3 | Data coning from the gas meter (timestamp) (total consumption) | m³ | gas_timestamp total_gas_consumption |

### Specific formats
The timestamps are not in epoch (seconds sinds the first of January 1970), but are formatted as `YYMMDDHHMMSS[WS]` where `W` is winter time and `S` is summer time. The year is in 2-digit format, 21 being 2021.\
The tarrif plans "dag" (day) and "nacht" (night) are also known as "full" and "reduced" tarrif.

## Install and run  the aplication
### Installation
1. Clone this repository somewhere on your local system.
```
cd <your-folder>
git clone https://gitlab.com/wimdh/smartmeter.git .
```
2. Create a virtual environment and install the required packages.
```
cd smartmeter
python3 -m venv .venv
source .vnev/bin/activate
pip install -r requirements.txt
# Only if you want to develop or want to run the tests
pip install -r requirements.dev.txt
```
### Run the application
Create a config file (change it to you needs), and run the application.
```
cp config.sample.ini your-configfile.ini
python app/main.py -c your-configfile.ini
```

### Start it at boot
You can start it at boot by adding the application to your cron, or you can use an application like `supervisor`.

## Links
* Specs for the user ports of the Fluvius digital meter: https://www.fluvius.be/sites/fluvius/files/2020-03/1901-fluvius-technical-specification-user-ports-digital-meter.pdf (English)
* More specs (Protocol description): https://www.netbeheernederland.nl/_upload/Files/Slimme_meter_15_a727fce1f1.pdf (English)
