from __future__ import print_function
from __future__ import unicode_literals

import re

from builtins import int
from builtins import object
from builtins import str

try:
    from types import SimpleNamespace
except:  # Python 2
    from argparse import Namespace as SimpleNamespace

import collections

from .error import (MethodNotFound, InvalidParameter)


class Scanner(object):
    """Class for scanning a varlink interface definition."""

    def __init__(self, string):
        if hasattr(re, "ASCII"):
            ASCII = re.ASCII
        else:
            ASCII = 0
        self.whitespace = re.compile(r'([ \t\n]|#.*$)+', ASCII | re.MULTILINE)
        self.docstring = re.compile(r'(?:.?)+#(.*)(?:\n|\r\n)')
        # FIXME: nested ()
        self.method_signature = re.compile(r'([ \t\n]|#.*$)*(\([^)]*\))([ \t\n]|#.*$)*->([ \t\n]|#.*$)*(\([^)]*\))',
                                           ASCII | re.MULTILINE)

        self.keyword_pattern = re.compile(r'\b[a-z]+\b|[:,(){}]|->|\[\]|\?|\[string\]\(\)|\[string\]', ASCII)
        self.patterns = {
            'interface-name': re.compile(r'[a-z]+(\.[a-z0-9][a-z0-9-]*)+'),
            'member-name': re.compile(r'\b[A-Z][A-Za-z0-9_]*\b', ASCII),
            'identifier': re.compile(r'\b[a-z][A-Za-z0-9_]*\b', ASCII),
        }

        self.string = string
        self.pos = 0
        self.current_doc = ""

    def get(self, expected):
        m = self.whitespace.match(self.string, self.pos)
        if m:
            doc = self.docstring.findall(self.string[m.start():m.end()])
            if len(doc):
                self.current_doc += str.join("\n", doc)
            self.pos = m.end()

        pattern = self.patterns.get(expected)
        if pattern:
            m = pattern.match(self.string, self.pos)
            if m:
                self.pos = m.end()
                return m.group(0)
        else:
            m = self.keyword_pattern.match(self.string, self.pos)
            if m and m.group(0) == expected:
                self.pos = m.end()
                return True

    def expect(self, expected):
        value = self.get(expected)
        if not value:
            raise SyntaxError("expected '{}'".format(expected))
        return value

    def end(self):
        m = self.whitespace.match(self.string, self.pos)
        if m:
            doc = self.docstring.findall(self.string[m.start():m.end()])
            if len(doc):
                self.current_doc += str.join("\n", doc)
            self.pos = m.end()

        return self.pos >= len(self.string)

    def read_type(self, lastmaybe=False):
        if self.get('?'):
            if lastmaybe:
                raise SyntaxError("double '??'")
            return _Maybe(self.read_type(lastmaybe=True))

        if self.get('[string]()'):
            return set()

        if self.get('[string]'):
            return _Dict(self.read_type())

        if self.get('[]'):
            return _Array(self.read_type())

        if self.get('object'):
            return _Object()

        if self.get('bool'):
            t = bool()
        elif self.get('int'):
            t = int()
        elif self.get('float'):
            t = float()
        elif self.get('string'):
            t = str()
        else:
            name = self.get('member-name')
            if name:
                t = _CustomType(name)
            else:
                t = self.read_struct()

        return t

    def read_struct(self):
        _isenum = None
        self.expect('(')
        fields = collections.OrderedDict()
        if not self.get(')'):
            while True:
                name = self.expect('identifier')
                if _isenum == None:
                    if self.get(':'):
                        _isenum = False
                        fields[name] = self.read_type()
                        if not self.get(','):
                            break
                        continue
                    elif self.get(','):
                        _isenum = True
                        fields[name] = True
                        continue
                    else:
                        raise SyntaxError("after '{}'".format(name))
                elif not _isenum:
                    try:
                        self.expect(':')
                        fields[name] = self.read_type()
                    except SyntaxError as e:
                        raise SyntaxError("after '{}': {}".format(name, e))
                else:
                    fields[name] = True

                if not self.get(','):
                    break
            self.expect(')')
        if _isenum:
            return _Enum(fields.keys())
        else:
            return _Struct(fields)

    def read_member(self):
        if self.get('type'):
            try:
                _name = self.expect('member-name')
            except SyntaxError:
                m = self.whitespace.match(self.string, self.pos)
                if m:
                    start = m.end()
                else:
                    start = self.pos
                m = self.whitespace.search(self.string, start)
                if m:
                    stop = m.start()
                else:
                    stop = start

                raise SyntaxError("'{}' not a valid type name.".format(self.string[start:stop]))
            try:
                _type = self.read_type()
            except SyntaxError as e:
                raise SyntaxError("in '{}': {}".format(_name, e))
            doc = self.current_doc
            self.current_doc = ""
            return _Alias(_name, _type, doc)
        elif self.get('method'):
            name = self.expect('member-name')
            # FIXME
            sig = self.method_signature.match(self.string, self.pos)
            if sig:
                sig = name + sig.group(0)
            in_type = self.read_struct()
            self.expect('->')
            out_type = self.read_struct()
            doc = self.current_doc
            self.current_doc = ""
            return _Method(name, in_type, out_type, sig, doc)
        elif self.get('error'):
            doc = self.current_doc
            self.current_doc = ""
            return _Error(self.expect('member-name'), self.read_type(), doc)
        else:
            raise SyntaxError('expected type, method, or error')


class _Object(object):
    pass


class _Struct(object):

    def __init__(self, fields):
        self.fields = collections.OrderedDict(fields)


class _Enum(object):

    def __init__(self, fields):
        self.fields = fields


class _Array(object):

    def __init__(self, element_type):
        self.element_type = element_type


class _Maybe(object):

    def __init__(self, element_type):
        self.element_type = element_type


class _Dict(object):

    def __init__(self, element_type):
        self.element_type = element_type


class _CustomType(object):

    def __init__(self, name):
        self.name = name


class _Alias(object):

    def __init__(self, name, varlink_type, doc=None):
        self.name = name
        self.type = varlink_type
        self.doc = doc


class _Method(object):

    def __init__(self, name, in_type, out_type, _signature, doc=None):
        self.name = name
        self.in_type = in_type
        self.out_type = out_type
        self.signature = _signature
        self.doc = doc


class _Error(object):

    def __init__(self, name, varlink_type, doc=None):
        self.name = name
        self.type = varlink_type
        self.doc = doc


class Interface(object):
    """Class for a parsed varlink interface definition."""

    def __init__(self, description):
        """description -- description string in varlink interface definition language"""
        self.description = description

        scanner = Scanner(description)
        scanner.expect('interface')
        self.name = scanner.expect('interface-name')
        self.doc = scanner.current_doc
        scanner.current_doc = ""
        self.members = collections.OrderedDict()
        while not scanner.end():
            member = scanner.read_member()
            self.members[member.name] = member

    def get_description(self):
        """return the description string in varlink interface definition language"""
        return self.description

    def get_method(self, name):
        method = self.members.get(name)
        if method and isinstance(method, _Method):
            return method
        raise MethodNotFound(name)

    def filter_params(self, parent_name, varlink_type, _namespaced, args, kwargs):
        # print("filter_params", type(varlink_type), repr(varlink_type), args, kwargs)

        if isinstance(varlink_type, _Maybe):
            if args == None:
                return None
            return self.filter_params(parent_name, varlink_type.element_type, _namespaced, args, kwargs)

        if isinstance(varlink_type, _Dict):
            if args == None:
                return {}

            if isinstance(args, dict):
                for (k, v) in args.items():
                    args[k] = self.filter_params(parent_name + '[' + k + ']', varlink_type.element_type, _namespaced, v,
                                                 None)
                return args
            else:
                InvalidParameter(parent_name)

        if isinstance(varlink_type, _CustomType):
            # print("CustomType", varlink_type.name)
            return self.filter_params(parent_name, self.members.get(varlink_type.name), _namespaced, args, kwargs)

        if isinstance(varlink_type, _Alias):
            # print("Alias", varlink_type.name)
            return self.filter_params(parent_name, varlink_type.type, _namespaced, args, kwargs)

        if isinstance(varlink_type, _Object):
            return args

        if isinstance(varlink_type, _Enum) and isinstance(args, str):
            # print("Returned str:", args)
            return args

        if isinstance(varlink_type, _Array):
            if args == None:
                return []

            return [self.filter_params(parent_name + '[]', varlink_type.element_type, _namespaced, x, None) for x in
                    args]

        if isinstance(varlink_type, set):
            # print("Returned set:", set(args))
            return set(args)

        if isinstance(varlink_type, str) and isinstance(args, str):
            # print("Returned str:", args)
            return args

        if isinstance(varlink_type, float) and (isinstance(args, float) or isinstance(args, int)):
            # print("Returned float:", args)
            return float(args)

        if isinstance(varlink_type, bool) and isinstance(args, bool):
            # print("Returned bool:", args)
            return args

        if isinstance(varlink_type, int) and (isinstance(args, float) or isinstance(args, int)):
            # print("Returned int:", args)
            if isinstance(args, float):
                return int(args + 0.5)
            return int(args)

        if not isinstance(varlink_type, _Struct):
            raise InvalidParameter(parent_name)
            # SyntaxError("Expected type %s, got %s with value '%s'" % (type(varlink_type), type(args),
            #                                                                args))

        if _namespaced:
            out = SimpleNamespace()
        else:
            out = {}

        varlink_struct = None
        if not isinstance(args, tuple):
            varlink_struct = args
            args = None

        for name in varlink_type.fields:
            if isinstance(args, tuple):
                if args:
                    val = args[0]
                    if len(args) > 1:
                        args = args[1:]
                    else:
                        args = None
                    ret = self.filter_params(parent_name + "." + name, varlink_type.fields[name], _namespaced, val,
                                             None)
                    if ret != None:
                        # print("SetOUT:", name)
                        if _namespaced:
                            setattr(out, name, ret)
                        else:
                            out[name] = ret
                    continue
                else:
                    if name in kwargs:
                        ret = self.filter_params(parent_name + "." + name, varlink_type.fields[name], _namespaced,
                                                 kwargs[name], None)
                        if ret != None:
                            # print("SetOUT:", name)
                            if _namespaced:
                                setattr(out, name, ret)
                            else:
                                out[name] = ret
                        continue

            if varlink_struct:
                if isinstance(varlink_struct, dict):
                    if name not in varlink_struct:
                        continue

                    val = varlink_struct[name]
                    ret = self.filter_params(parent_name + "." + name, varlink_type.fields[name], _namespaced, val,
                                             None)
                    if ret != None:
                        # print("SetOUT:", name)
                        if _namespaced:
                            setattr(out, name, ret)
                        else:
                            out[name] = ret
                elif hasattr(varlink_struct, name):
                    val = getattr(varlink_struct, name)
                    ret = self.filter_params(parent_name + "." + name, varlink_type.fields[name], _namespaced, val,
                                             None)
                    if ret != None:
                        # print("SetOUT:", name)
                        if _namespaced:
                            setattr(out, name, ret)
                        else:
                            out[name] = ret
                else:
                    continue

        return out
