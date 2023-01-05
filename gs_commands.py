"""
"""
import json
from lib.logs import unpack_beacon
from lib.radio_utils.disk_buffered_message import DiskBufferedMessage
from lib.radio_utils import headers
from lib.radio_utils.commands import super_secret_code, commands, _pack, _unpack
from shell_utils import bold, normal, red
import time
try:
    import calendar
    HAS_CALENDAR = True
except:
    HAS_CALENDAR = False


commands_by_name = {
    commands[cb]["name"]:
    {"bytes": cb, "will_respond": commands[cb]["will_respond"], "has_args": commands[cb]["has_args"]}
    for cb in commands.keys()}


def send_command(radio, command_bytes, args, will_respond, max_rx_fails=10, debug=False):
    success = False
    response = None
    header = None
    msg = bytes([headers.COMMAND]) + super_secret_code + command_bytes + bytes(args, 'utf-8')
    if radio.send_with_ack(msg, debug=debug):
        if debug:
            print('Successfully sent command')
        if will_respond:
            if debug:
                print('Waiting for response')
            header, response = wait_for_message(radio, max_rx_fails=10, debug=debug)
            if header is not None:
                success = True
                if debug:
                    print_message(header, response)
            else:
                success = False
        else:
            success = True
    else:
        if debug:
            print('Failed to send command')
        success = False
    return success, header, response


def move_file(radio, source_path, destination_path, debug=False):
    arg_string = json.dumps([source_path, destination_path])
    success, _, response = send_command(
        radio,
        commands_by_name["MOVE_FILE"]["bytes"],
        arg_string,
        commands_by_name["MOVE_FILE"]["will_respond"],
        debug=debug)

    if "success" in str(response).lower():
        success &= True
    else:
        success &= False

    if debug:
        if success:
            print(f"{bold}MOVE_FILE Response:{normal} {response}")
        else:
            print(f"{bold}MOVE_FILE Response:{normal} {red}FAILED{normal}")

    return success


def request_file(radio, path, debug=False):
    success, header, response = send_command(
        radio,
        commands_by_name["REQUEST_FILE"]["bytes"],
        path,
        commands_by_name["REQUEST_FILE"]["will_respond"],
        debug=debug)

    if header == headers.DEFAULT:
        success &= False  # this is not a DiskBufferedMessage - an error must have occurred

    if debug:
        if success:
            print(f"{bold}REQUEST_FILE:{normal} {path}\n\nContents:\n{response}")
        else:
            print(f"{bold}REQUEST_FILE:{normal} {path} {red}FAILED{normal}")

    return success, header, response


def upload_file(radio, local_path, satellite_path, debug=False):
    msg = DiskBufferedMessage(0, local_path)

    success = send_message(radio, msg, debug=debug)

    if success:
        success &= move_file(radio, "/sd/disk_buffered_message", satellite_path, debug=debug)
    return success


def request_beacon(radio, debug=False):
    success, header, response = send_command(
        radio,
        commands_by_name["REQUEST_BEACON"]["bytes"],
        "",
        commands_by_name["REQUEST_BEACON"]["will_respond"],
        debug=debug)

    if success and header == headers.BEACON:
        return True, beacon_str(response)
    else:
        return False, None


def set_time(radio, unix_time=None, debug=False):
    """ Update the real time clock on the satellite using either a given value or the system time"""
    if unix_time is None:
        if HAS_CALENDAR:
            unix_time = calendar.timegm(time.gmtime())
        else:
            print(f"GMT unavailable - using local time")
            unix_time = time.mktime(time.localtime())

    if debug:
        print(f"Updating time to {unix_time}")

    args = _pack(unix_time)

    success, _, _ = send_command(
        radio,
        commands_by_name["SET_RTC_UTIME"]["bytes"],
        args,
        commands_by_name["SET_RTC_UTIME"]["will_respond"],
        debug=debug
    )

    return success


def get_time(radio, debug=False):
    success, header, response = send_command(
        radio,
        commands_by_name["GET_RTC_UTIME"]["bytes"],
        "",
        commands_by_name["GET_RTC_UTIME"]["will_respond"],
        debug=debug)

    if success and header == headers.DEFAULT:
        sat_time = _unpack(response)
        return True, sat_time
    else:
        return False, None


def receive(rfm9x, with_ack=True, debug=False):
    """Recieve a packet.  Returns None if no packet was received.
    Otherwise returns (header, payload)"""
    packet = rfm9x.receive(with_ack=with_ack, with_header=True, debug=debug)
    if packet is None:
        return None
    return packet[0:6], packet[6:]


def send_message(radio, msg, debug=False):
    success = True
    while True:
        packet, with_ack = msg.packet()

        if debug:
            debug_packet = str(packet)[:20] + "...." if len(packet) > 23 else packet
            print(f"Sending packet: {debug_packet}, with_ack: {with_ack}")

        if with_ack:
            got_ack = radio.send_with_ack(packet, debug=True)
            if got_ack:
                msg.ack()
            else:
                success = False
                break
        else:
            radio.send(packet, keep_listening=True)

        if msg.done():
            break

    return success


class _data:

    def __init__(self):
        self.msg = bytes([])
        self.msg_last = bytes([])
        self.cmsg = bytes([])
        self.cmsg_last = bytes([])


def wait_for_message(radio, max_rx_fails=10, debug=False):
    data = _data()

    rx_fails = 0
    while True:
        res = receive(radio, debug=debug)

        if res is None:
            rx_fails += 1
            if rx_fails > max_rx_fails:
                print("wait_for_message: max_rx_fails hit")
                return None, None
            else:
                continue
        else:
            rx_fails = 0

        header, payload = res

        oh = header[5]
        if oh == headers.DEFAULT or oh == headers.BEACON:
            return oh, payload
        elif oh == headers.MEMORY_BUFFERED_START or oh == headers.MEMORY_BUFFERED_MID or oh == headers.MEMORY_BUFFERED_END:
            handle_memory_buffered(oh, data, payload)
            if oh == headers.MEMORY_BUFFERED_END:
                return headers.MEMORY_BUFFERED_START, data.msg

        elif oh == headers.DISK_BUFFERED_START or oh == headers.DISK_BUFFERED_MID or oh == headers.DISK_BUFFERED_END:
            handle_disk_buffered(oh, data, payload)
            if oh == headers.DISK_BUFFERED_END:
                return headers.DISK_BUFFERED_START, data.cmsg
        else:
            print(f"Unrecognized header {oh}")
            return oh, payload


def print_message(header, message):
    if header == headers.DEFAULT:
        print(f"Default: {message}")
    elif header == headers.BEACON:
        print(beacon_str(message))
    elif header == headers.MEMORY_BUFFERED_START or header == headers.DISK_BUFFERED_START:
        print(f"Buffered:\n\t{message}")
    else:
        print(f"Header {header} unknown: {message}")


def beacon_str(beacon):
    beacon_dict = unpack_beacon(beacon)
    bs = f"\n{bold}Beacon:{normal}"
    for bk in beacon_dict:
        bv = beacon_dict[bk]
        if isinstance(bv, float):
            bvstr = f"{bv:.4}"
        else:
            bvstr = str(bv)
        bs += f"\t{bk:.<35} {bvstr}\n"
    return bs


def handle_memory_buffered(header, data, payload):
    if header == headers.MEMORY_BUFFERED_START:
        data.msg_last = payload
        data.msg = payload
    else:
        if payload != data.msg_last:
            data.msg += payload
        else:
            data.debug('Repeated payload')

    if header == headers.MEMORY_BUFFERED_END:
        data.msg_last = bytes([])
        data.msg = str(data.msg, 'utf-8')
        print(data.msg)


def handle_disk_buffered(header, data, response):
    if header == headers.DISK_BUFFERED_START:
        data.cmsg = response
        data.cmsg_last = response
    else:
        if response != data.cmsg_last:
            data.cmsg += response
        else:
            data.debug('Repeated payload')
        data.cmsg_last = response

    if header == headers.DISK_BUFFERED_END:
        data.cmsg_last = bytes([])
        data.cmsg = str(data.cmsg, 'utf-8')
        print('Recieved disk buffered message')
        print(data.cmsg)
