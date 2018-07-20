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
import sys

import varlink


def varlink_call(args):
    deli = args.METHOD.rfind(".")
    if deli == -1:
        print("No method found", file=sys.stderr)
        sys.exit(1)

    method = args.METHOD[deli + 1:]
    interface = args.METHOD[:deli]

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

    got = False
    try:
        with client.open(interface) as con:
            out = {'method': interface + '.' + method, 'more': args.more, 'parameters': json.loads(args.ARGUMENTS)}
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
    print(interface.description)


def varlink_info(args):
    if args.ADDRESS:
        deli = args.ADDRESS.rfind("/")
        if deli != -1:
            address = args.ADDRESS
            client = varlink.Client.new_with_address(address)
        else:
            interface = args.ADDRESS
            if args.activate:
                client = varlink.Client.new_with_activate(shlex.split(args.activate))
            elif args.bridge:
                client = varlink.Client.new_with_bridge(shlex.split(args.bridge))
            else:
                client = varlink.Client.new_with_resolved_interface(interface, args.resolver)

        client.get_interfaces()
        info = client.info
        print("Vendor:", info["vendor"])
        print("Product:", info["product"])
        print("Version:", info["version"])
        print("URL:", info["url"])
        print("Interfaces:")
        for i in info["interfaces"]:
            print("  ", i)

        del client
    else:
        if args.bridge:
            client = varlink.Client.new_with_bridge(shlex.split(args.bridge))
        else:
            client = varlink.Client.new_with_address("unix:/run/org.varlink.resolver")

        with client:
            info = client.open("org.varlink.resolver").GetInfo()
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
    parser_info.add_argument('ADDRESS')
    parser_info.set_defaults(func=varlink_info)

    parser_help = subparsers.add_parser('help', help='Print interface description or service information')
    parser_help.add_argument('INTERFACE')
    parser_help.set_defaults(func=varlink_help)

    parser_call = subparsers.add_parser('call', help='Call a method')
    parser_call.add_argument('-m', '--more', action='store_true', help='wait for multiple method returns if supported')
    parser_call.add_argument('METHOD')
    parser_call.add_argument('ARGUMENTS')
    parser_call.set_defaults(func=varlink_call)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_usage(sys.stderr)
        sys.exit(1)

    args.func(args)
