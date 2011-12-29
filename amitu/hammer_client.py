"""
HammerClient
============

Example::

    from amitu.hammer_client import HammerClient

    hammerlib = HammerClient("localhost", 8081, sessionid="foo")

    def opened(cmd, type, data):
        print "opened"
        hammerlib.send("pingpong", "ping", {"text": "asd"})
        print "sent ping"

    def pong(cmd, type, data):
        print "pong: ", data["text"]

    hammerlib.bind("hammerlib", "opened", opened)
    hammerlib.bind("pingpong", "pong", pong)

    hammerlib.run()

"""
from amitu.socketio_client import SocketIOClient
import json


class HammerClient(object):
    def __init__(self, server, port, sessionid="", *args, **kw):
        self.sock = SocketIOClient(server, port, *args, **kw)
        self.sessionid = sessionid
        self.sock.on("connect", self._connect)
        self.sock.on("server", self._server)
        self.sock.on("close", self._close)
        self.binds = {}
        self.app_binds = {}
        self.bind("hammerlib", "connected", self._connected)

    def run(self):
        while True:
            self.sock.run()

    def bind(self, cmd, type, callback):
        self.binds.setdefault("%s:%s" % (cmd, type), []).append(callback)

    def unbind(self, cmd, type, callback):
        self.binds["%s:%s" % (cmd, type)].remove(callback)

    def bind_app(self, cmd, callback):
        self.app_binds.setdefault(cmd, []).append(callback)

    def unbind_app(self, cmd, callback):
        self.app_binds[cmd].remove(callback)

    def send(self, cmd, type, data):
        if not isinstance(data, basestring):
            data = json.dumps(data)
        self.sock.emit(u"browser", u"%s:%s:%s\r\n" % (cmd, type, data))

    def _connect(self):
        self.send("hammerlib", "get_clientid", self.sessionid)

    def _fire_app_event(self, cmd, type, message):
        for callback in self.app_binds.get(cmd, []):
            callback(cmd, type, message)

    def _fire_event(self, cmd, type, message):
        for callback in self.binds.get("%s:%s" % (cmd, type), []):
            callback(cmd, type, message)

    def _fire(self, cmd, type, message):
        self._fire_event(cmd, type, message)
        self._fire_app_event(cmd, type, message)

    def _connected(self, cmd, type, data):
        self._fire("hammerlib", "opened", "")

    def _server(self, data):
        cmd, type, data = data["message"].split(":", 2)
        data = json.loads(data)
        print cmd, type, data
        self._fire(cmd, type, data)

    def _close(self):
        self._fire("hammerlib", "closed", "")


