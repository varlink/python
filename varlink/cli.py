# /usr/bin/env python
"""varlink cli tool

Call with:
$ python -m varlink.cli --help

"""

from __future__ import print_function
from __future__ import unicode_literals

import argparse
import json
import sys

import varlink


def varlink_call(args):
    deli = args.METHOD.rfind(".")
    if deli == -1:
        print("No method found", file=sys.stderr)
        sys.exit(1)

    method = args.METHOD[deli + 1:]
    interface = args.METHOD[:deli]

    deli = args.METHOD.find("/")
    if deli != -1:
        address = interface[:deli]
        interface = interface[deli + 1:]
        client = varlink.Client(address)
    else:
        client = varlink.Client(resolve_interface=interface, resolver=args.resolver)

    got = False
    try:
        with client.open(interface) as con:
            out = {'method': interface + '.' + method, 'more': args.more, 'parameters': json.loads(args.ARGUMENTS)}
            con._send_message(json.dumps(out, cls=varlink.VarlinkEncoder).encode('utf-8'))
            more = True
            while more:
                (message, more) = con._next_varlink_message()
                if message:
                    print(message)
                    got = True
    except varlink.VarlinkError as e:
        print(e, file=sys.stderr)
    except BrokenPipeError:
        if not got or args.more:
            print("Connection closed")
            sys.exit(1)


def varlink_help(args):
    deli = args.INTERFACE.rfind("/")
    if deli != -1:
        address = args.INTERFACE[:deli]
        interface = args.INTERFACE[deli + 1:]
        client = varlink.Client(address)
    else:
        interface = args.INTERFACE
        client = varlink.Client(resolve_interface=interface, resolver=args.resolver)

    ifaces = client.get_interfaces()
    if interface in ifaces:
        print(ifaces[interface].description)


def varlink_info(args):
    with varlink.Client(args.ADDRESS) as client:
        info = client.info
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
