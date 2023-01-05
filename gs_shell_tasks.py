from gs_commands import *
from shell_utils import *


def send_command_task(radio, command_bytes, args, will_respond, debug=False):
    success, header, response = send_command(radio, command_bytes, args, will_respond, debug=debug)
    if success:
        print("Command successful")
        if header is not None and response is not None:
            print_message(header, response)
    else:
        print("Command failed")


def get_time_task(radio, debug=False):
    success, sat_time = get_time(radio, debug=debug)
    if success:
        print(f"Time = {sat_time}")
    else:
        print("Command failed")


def read_loop(radio):

    while True:
        header, message = wait_for_message(radio)
        print_message(header, message)


def human_time_stamp():
    """Returns a human readable time stamp in the format: 'year.month.day hour:min'
    Gets the local time."""
    t = time.localtime()
    return f'{t.tm_year:4}.{t.tm_mon:02}.{t.tm_mday:02}.{t.tm_hour:02}:{t.tm_min:02}:{t.tm_sec:02}'


def timestamped_log_print(str, printcolor=normal, logname="./test_log.txt"):
    """
    Timestamp, print to stdout and log str to a file
    """
    timestamp = human_time_stamp()

    print(f"[{yellow}{timestamp}{normal}]\t" +
          f"{printcolor}{str}{normal}")

    if logname is not None and not logname == "":
        try:
            with open(logname, "a") as f:
                f.write(f"[{timestamp}]\t" +
                        f"{str}" + "\n")
        except OSError as e:
            print(e)


def get_beacon(radio, debug=False, logname=None):
    timestamped_log_print(f"Requesting beacon...")
    success, bs = request_beacon(radio, debug=debug)
    if success:
        timestamped_log_print(f"Successful beacon request", printcolor=green, logname=logname)
        timestamped_log_print(bs, logname=logname)
    else:
        timestamped_log_print(f"Failed beacon request", printcolor=red, logname=logname)
