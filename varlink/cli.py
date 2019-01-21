# /usr/bin/env python
"""varlink cli tool

Call with:
$ python -m varlink.cli --help

"""

from __future__ import print_function
from __future__ import unicode_literals

import argparse
import json
import shlex
import socket
import sys

import varlink


def varlink_call(args):
    deli = args.METHOD.rfind(".")
    if deli == -1:
        print("No method found", file=sys.stderr)
        sys.exit(1)

    method = args.METHOD[deli + 1:]
    interface = args.METHOD[:deli]

    def new_client(interface):
        deli = interface.rfind("/")
        if deli != -1:
            address = interface[:deli]
            interface = interface[deli + 1:]
            client = varlink.Client.new_with_address(address)
        else:
            if args.activate:
                client = varlink.Client.new_with_activate(shlex.split(args.activate))
            elif args.bridge:
                client = varlink.Client.new_with_bridge(shlex.split(args.bridge))
            else:
                client = varlink.Client.new_with_resolved_interface(interface, args.resolver)
        return client

    with new_client(interface) as client:
        got = False
        try:
            with client.open(interface) as con:
                out = {'method': interface + '.' + method, 'more': args.more, 'parameters': json.loads(args.ARGUMENTS or "{}" )}
                con._send_message(json.dumps(out, cls=varlink.VarlinkEncoder).encode('utf-8'))
                more = True
                while more:
                    (message, more) = con._next_varlink_message()
                    if message:
                        print(json.dumps(message, cls=varlink.VarlinkEncoder, indent=2, sort_keys=True))
                        got = True
        except varlink.VarlinkError as e:
            print(e, file=sys.stderr)
        except varlink.BrokenPipeError:
            if not got or args.more:
                print("Connection closed")
                sys.exit(1)

def varlink_bridge(args):
    message = b''
    last_interface = None
    con = None
    client = None

    if args.connect:
        client = varlink.Client.new_with_address(args.connect)
        con = client.open_connection()
    elif args.bridge:
        client = varlink.Client.new_with_bridge(shlex.split(args.bridge))
        con = client.open_connection()
    elif args.activate:
        client = varlink.Client.new_with_activate(shlex.split(args.activate))
        con = client.open_connection()
    else:
        print("No --connect or --bridge or --activate")


    if hasattr(sys.stdout, 'buffer'):
        stdout = sys.stdout.buffer
    else:
        stdout = sys.stdout

    if hasattr(sys.stdin, 'buffer'):
        stdin = sys.stdin.buffer
    else:
        stdin = sys.stdin

    while not sys.stdin.closed:
        c = stdin.read(1)

        if c == b'':
            break

        if c != b'\0':
            message += c
            continue

        req = json.loads(message.decode('utf-8'))

        if not args.connect and not args.activate and not args.bridge:
            if req['method'] == "org.varlink.service.GetInfo":
                req['method'] = "org.varlink.resolver.GetInfo"

            interface_name, _, method_name = req.get('method', '').rpartition('.')

            if req['method'] == "org.varlink.service.GetInterfaceDescription":
                resolving_interface = req['parameters']['interface']
            else:
                resolving_interface = interface_name

            if not interface_name or not method_name:
                stdout.write(json.dumps(varlink.InterfaceNotFound(interface_name), cls=varlink.VarlinkEncoder).encode(
                    'utf-8') + b'\0')
                sys.stdout.flush()
                continue

            if last_interface != resolving_interface:
                if con:
                    if hasattr(con, 'shutdown'):
                        con.shutdown(socket.SHUT_RDWR)
                    else:
                        con.close()

                if client:
                    client.cleanup()

                try:
                    client = varlink.Client.new_with_resolved_interface(resolving_interface,
                                                                        resolver_address=args.resolver)
                except varlink.VarlinkError as e:
                    stdout.write(
                        json.dumps(e, cls=varlink.VarlinkEncoder).encode(
                            'utf-8') + b'\0')
                    sys.stdout.flush()
                    continue

                con = client.open_connection()
                last_interface = resolving_interface

        if hasattr(con, "send"):
            con.send(message + b'\0')
        else:
            con.write(message + b'\0')

        if req.get("oneway", False):
            continue

        message = b''

        ret_message = b''
        while True:
            c = con.recv(1)

            if c == b'':
                break

            if c != b'\0':
                ret_message += c
                continue

            stdout.write(ret_message + b'\0')

            sys.stdout.flush()

            ret = json.loads(ret_message.decode('utf-8'))
            ret_message = b''

            if not ret.get('continues', False):
                break

            if ret.get('upgraded', False):
                raise NotImplementedError("Bridging upgraded connection not yet supported")


def varlink_help(args):
    deli = args.INTERFACE.rfind("/")
    if deli != -1:
        address = args.INTERFACE[:deli]
        interface_name = args.INTERFACE[deli + 1:]
        client = varlink.Client.new_with_address(address)
    else:
        interface_name = args.INTERFACE
        if args.activate:
            client = varlink.Client.new_with_activate(shlex.split(args.activate))
        elif args.bridge:
            client = varlink.Client.new_with_bridge(shlex.split(args.bridge))
        else:
            client = varlink.Client.new_with_resolved_interface(interface_name, args.resolver)

    interface = client.get_interface(interface_name)
    del client
    print(interface.description)

def varlink_info(args):
    if args.ADDRESS:
        client = varlink.Client.new_with_address(args.ADDRESS)
    elif args.bridge:
        client = varlink.Client.new_with_bridge(shlex.split(args.bridge))
    elif args.activate:
        client = varlink.Client.new_with_activate(shlex.split(args.activate))
    else:
        print("No ADDRESS or --bridge or --activate")


    client.get_interfaces()
    info = client.info
    del client
    print("Vendor:", info["vendor"])
    print("Product:", info["product"])
    print("Version:", info["version"])
    print("URL:", info["url"])
    print("Interfaces:")
    for i in info["interfaces"]:
        print("  ", i)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(title="commands")
    parser.add_argument('-r', '--resolver', default=None, help='address of the resolver')
    parser.add_argument('-A', '--activate', default=None,
                        help='Service to socket-activate and connect to. '
                             'The temporary UNIX socket address is exported as $VARLINK_ADDRESS.')
    parser.add_argument('-b', '--bridge', default=None, help='Command to execute and connect to')

    parser_info = subparsers.add_parser('info', help='Print information about a service')
    parser_info.add_argument('ADDRESS', nargs='?')
    parser_info.set_defaults(func=varlink_info)

    parser_help = subparsers.add_parser('help', help='Print interface description or service information')
    parser_help.add_argument('INTERFACE')
    parser_help.set_defaults(func=varlink_help)

    parser_bridge = subparsers.add_parser('bridge', help='Bridge varlink messages to services on this machine')
    parser_bridge.add_argument('-c', '--connect', default=None, help='Optional varlink address to connect to, '
                                                                     'without using the resolver.')
    parser_bridge.set_defaults(func=varlink_bridge)

    parser_call = subparsers.add_parser('call', help='Call a method')
    parser_call.add_argument('-m', '--more', action='store_true', help='wait for multiple method returns if supported')
    parser_call.add_argument('METHOD')
    parser_call.add_argument('ARGUMENTS', nargs='?', default="")
    parser_call.set_defaults(func=varlink_call)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_usage(sys.stderr)
        sys.exit(1)

    args.func(args)
