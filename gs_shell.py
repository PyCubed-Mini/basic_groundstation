"""
Provides a basic shell-like interface to send and receive data from the satellite
"""
import sys  # noqa
sys.path.append("lib")  # noqa

from shell_utils import *
from gs_shell_tasks import *
from gs_setup import *
import tasko

try:
    import supervisor
except ImportError:
    supervisor = None


# prevent board from reloading in the middle of the test
if supervisor is not None:
    supervisor.disable_autoreload()

prompt_options = {"Receive loop": ("r", "receive"),
                  "Beacon request loop": ("b", "beacon"),
                  "Upload file": ("u", "upload"),
                  "Request file": ("rf", "request"),
                  "Send command": ("c", "command"),
                  "Set time": ("st", "settime"),
                  "Get time": ("gt", "gettime"),
                  "Help": ("h", "print_help"),
                  "Toggle verbose debug prints": ("v", "verbose"),
                  "Quit": ("q", "quit")}
flattend_prompt_options = [v for pov in prompt_options.values() for v in pov]


def print_help():
    print(f"\n{yellow}Groundstation shell help:{normal}")
    for po in prompt_options:
        print(f"{bold}{po}{normal}: {prompt_options[po]}")

# setup


print(f"\n{bold}{yellow}PyCubed-Mini Groundstation Shell{normal}\n")

board_str = get_input_discrete(
    f"""Select the board/radio:
        {bold}(s){normal} satellite,
        {bold}(f){normal} feather,
        {bold}(p){normal} raspberry pi,
        {bold}(t){normal} RPiGS TX,
        {bold}(r){normal} RPiGS RX,
        """,
    ["s", "f", "p", "t", "r"]
)

if board_str == "s":
    spi, cs, reset = satellite_spi_config()
    print(f"{bold}{green}Satellite{normal} selected")
elif board_str == "f":
    spi, cs, reset = feather_spi_config()
    print(f"{bold}{green}Feather{normal} selected")
elif board_str == "p":
    spi, cs, reset = pi_spi_config()
    print(f"{bold}{green}Raspberry Pi{normal} selected")
elif board_str == "t":
    spi, cs, reset = rpigs_tx_spi_config()
    print(f"{bold}{green}Raspberry Pi{normal} selected")
elif board_str == "r":
    spi, cs, reset = rpigs_rx_spi_config()
    print(f"{bold}{green}Raspberry Pi{normal} selected")
else:
    raise ValueError(f"Board string {board_str} invalid")


radio = initialize_radio(spi, cs, reset)

print_radio_configuration(radio)

if get_input_discrete(
        f"Change radio parameters? {bold}(y/N){normal}", ["", "y", "n"]) == "y":
    manually_configure_radio(radio)
    print_radio_configuration(radio)


print_help()


def gs_shell_main_loop():
    verbose = True
    while True:
        try:
            choice = get_input_discrete(f"\n{blue}Choose an action{normal}", flattend_prompt_options)
            if choice in prompt_options["Receive loop"]:
                print("Entering receive loop. CTRL-C to exit")
                while True:
                    tasko.add_task(read_loop(radio, debug=verbose), 1)
                    tasko.run()

            elif choice in prompt_options["Beacon request loop"]:
                beacon_period = get_input_range("Request period (seconds)", (10, 1000), allow_default=False)
                beacon_frequency_hz = 1.0 / float(beacon_period)
                logname = input("log file name (empty to not log) = ")
                def get_beacon_noargs(): return get_beacon(radio, debug=verbose, logname=logname)
                tasko.schedule(beacon_frequency_hz, get_beacon_noargs, 10)
                tasko.run()

            elif choice in prompt_options["Upload file"]:
                source = input('source path = ')
                dest = input('destination path = ')
                tasko.add_task(upload_file(radio, source, dest, debug=verbose), 1)
                tasko.run()
                tasko.reset()

            elif choice in prompt_options["Request file"]:
                source = input('source path = ')
                tasko.add_task(request_file(radio, source, debug=verbose), 1)
                tasko.run()
                tasko.reset()

            elif choice in prompt_options["Send command"]:
                command_name = get_input_discrete("Select a command", list(commands_by_name.keys())).upper()
                command_bytes = commands_by_name[command_name]["bytes"]
                will_respond = commands_by_name[command_name]["will_respond"]
                args = input('arguments = ')

                tasko.add_task(send_command_task(radio, command_bytes, args, will_respond, debug=verbose), 1)
                tasko.run()
                tasko.reset()

            elif choice in prompt_options["Set time"]:
                while True:
                    t = input("seconds since epoch (empty for system time) = ")
                    if t == "":
                        t = None
                        break
                    else:
                        try:
                            t = int(t)
                            break
                        except ValueError:
                            print("Invalid time - must be empty or an integer")

                tasko.add_task(set_time(radio, t, debug=verbose), 1)
                tasko.run()
                tasko.reset()

            elif choice in prompt_options["Get time"]:
                tasko.add_task(get_time_task(radio, debug=verbose), 1)
                tasko.run()
                tasko.reset()

            elif choice in prompt_options["Help"]:
                print_help()

            elif choice in prompt_options["Toggle verbose debug prints"]:
                verbose = not verbose
                print(f"Verbose: {verbose}")

            elif choice in prompt_options["Quit"]:
                break

        except KeyboardInterrupt:
            print(f"\n{red}Enter q to quit{normal}")
            tasko.reset()
            pass


gs_shell_main_loop()
