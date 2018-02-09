# /usr/bin/env python3

import varlink


def test_scanner_1():
    interface = varlink.Interface("""# Example Varlink service
interface org.varlink.example.more

# Enum, returning either start, progress or end
# progress: [0-100]
type State (
     start: bool,
     progress: int,
     end: bool
)

# Returns the same string
method Ping(ping : string) -> (pong: string)

# Dummy progress method
# n: number of progress steps
method TestMore(n : int) -> (state: State)

# Stop serving
method StopServing() -> ()

# Something failed
error ActionFailed (reason: string)
""")
    assert interface.name == "org.varlink.example.more"
    assert interface.get_method("Ping") != None
    assert interface.get_method("TestMore") != None
    assert interface.get_method("StopServing") != None
    assert isinstance(interface.members.get("ActionFailed"), varlink._Error)
    assert isinstance(interface.members.get("State"), varlink._Alias)
