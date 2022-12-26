"""
Simple script for doing typical groundstation operations as 
part of a day in the life test.
"""
from gs_setup import *
from gs_shell_tasks import *
from shell_utils import bold, normal, red, green, yellow, blue, get_input_discrete, manually_configure_radio, print_radio_configuration
import tasko
import time
import sys
sys.path.append("lib")


log_filename = "./test_logs.txt"
beacon_frequency_hz = 1.0 / 20
debug = False

board_str = get_input_discrete(
    f"Select the board {bold}(s){normal}atellite, {bold}(f){normal}eather, {bold}(r){normal}aspberry pi",
    ["s", "f", "r"]
)

if board_str == "s":
    cs, reset = satellite_cs_reset()
    print(f"{bold}{green}Satellite{normal} selected")
elif board_str == "f":
    cs, reset = feather_cs_reset()
    print(f"{bold}{green}Feather{normal} selected")
else:  # board_str == "r"
    cs, reset = pi_cs_reset()
    print(f"{bold}{green}Raspberry Pi{normal} selected")

radio = initialize_radio(cs, reset)

print_radio_configuration(radio)

if get_input_discrete(
        f"Change radio parameters? {bold}(y/N){normal}", ["", "y", "n"]) == "y":
    manually_configure_radio(radio)
    print_radio_configuration(radio)


def human_time_stamp():
    """Returns a human readable time stamp in the format: 'year.month.day hour:min'
    Gets the local time."""
    t = time.localtime()
    return f'{t.tm_year:4}.{t.tm_mon:02}.{t.tm_mday:02}.{t.tm_hour:02}:{t.tm_min:02}:{t.tm_sec:02}'


def log_print(str, printcolor=normal):
    """
    Timestamp, print to stdout and log str to a file
    """
    timestamp = human_time_stamp()

    print(f"[{yellow}{timestamp}{normal}]\t" +
          f"{printcolor}{str}{normal}")

    try:
        with open(log_filename, "a") as f:
            f.write(f"[{timestamp}]\t" +
                    f"{str}" + "\n")
    except OSError as e:
        print(e)
        pass


async def get_beacon():
    log_print(f"Requesting beacon...")
    success, bs = await request_beacon(radio, debug=debug)
    if success:
        log_print(f"Successful beacon request", printcolor=green)
        log_print(bs)
    else:
        log_print(f"Failed beacon request", printcolor=red)


tasko.schedule(beacon_frequency_hz, get_beacon, 10)
tasko.run()
