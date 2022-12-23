"""
"""
import json
from lib.logs import unpack_beacon
from lib.radio_utils.disk_buffered_message import DiskBufferedMessage
from lib.radio_utils import headers
from lib.radio_utils.commands import super_secret_code, commands
from shell_utils import bold, normal, red

commands_by_name = {
    commands[cb]["name"]:
    {"bytes": cb, "will_respond": commands[cb]["will_respond"], "has_args": commands[cb]["has_args"]}
    for cb in commands.keys()}


async def send_command(radio, command_bytes, args, will_respond, debug=False):
    success = False
    response = None
    header = None
    msg = bytes([headers.COMMAND]) + super_secret_code + command_bytes + bytes(args, 'utf-8')
    if await radio.send_with_ack(msg, debug=debug):
        if debug:
            print('Successfully sent command')
        if will_respond:
            if debug:
                print('Waiting for response')
            header, response = await wait_for_message(radio)
            if debug:
                print_message(type, response)
        success = True
    else:
        if debug:
            print('Failed to send command')
        success = False
    return success, header, response


async def move_file(radio, source_path, destination_path, debug=False):
    arg_string = json.dumps([source_path, destination_path])
    success, _, response = await send_command(
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


async def request_file(radio, path, debug=False):
    success, header, response = await send_command(
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


async def upload_file(radio, local_path, satellite_path, debug=False):
    msg = DiskBufferedMessage(0, local_path)

    success = await send_message(radio, msg, debug=debug)

    if success:
        success &= await move_file(radio, "/sd/disk_buffered_message", satellite_path, debug=debug)
    return success


async def request_beacon(radio, debug=False):
    success, header, response = await send_command(
        radio,
        commands_by_name["REQUEST_BEACON"]["bytes"],
        "",
        commands_by_name["REQUEST_BEACON"]["will_respond"],
        debug=debug)

    if success and header == headers.BEACON:
        return True, beacon_str(response)
    else:
        return False, None


async def receive(rfm9x, with_ack=True):
    """Recieve a packet.  Returns None if no packet was received.
    Otherwise returns (header, payload)"""
    packet = await rfm9x.receive(with_ack=with_ack, with_header=True, debug=True)
    if packet is None:
        return None
    return packet[0:6], packet[6:]


async def send_message(radio, msg, debug=False):
    success = True
    while True:
        packet, with_ack = msg.packet()

        if debug:
            debug_packet = str(packet)[:20] + "...." if len(packet) > 23 else packet
            print(f"Sending packet: {debug_packet}, with_ack: {with_ack}")

        if with_ack:
            got_ack = await radio.send_with_ack(packet, debug=True)
            if got_ack:
                msg.ack()
            else:
                success = False
                break
        else:
            await radio.send(packet, keep_listening=True)

        if msg.done():
            break

    return success


class _data:

    def __init__(self):
        self.msg = bytes([])
        self.msg_last = bytes([])
        self.cmsg = bytes([])
        self.cmsg_last = bytes([])


async def wait_for_message(radio):
    data = _data()

    while True:
        res = await receive(radio)
        if res is None:
            continue
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
        print(f"Unknown: {message}")


def beacon_str(beacon):
    beacon_dict = unpack_beacon(beacon)
    bs = "\n{bold}Beacon:{normal}"
    for bk in beacon_dict:
        bv = beacon_dict[bk]
        if isinstance(bv, float):
            bvstr = f"{bv:.4}"
        else:
            bvstr = str(bv)
        bs += f"\t{bk:.<35}" + " " + bvstr
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
