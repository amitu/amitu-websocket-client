"""
SocketIOClient
==============

Example::

    from amitu.socketio_client import SocketIOClient

    sock = SocketIOClient("localhost", 8081)

    def my_connect():
        print("opened!")
        sock.emit("browser", "data!")
        sock.on("server", on_server)

    def on_server(data):
        print data

    sock.on("connect", my_connect)
    sock.run()


See ThreadedSocketIOClient below for a different usage example.

"""
import amitu.websocket_client
import httplib
import json
import time
import socket
import threading
from Queue import Queue

import logging
logger = logging.getLogger(__name__)


class SocketIOPacket(object):
    def __init__(self, id="", endpoint="", data=None):
        self.id = id
        self.endpoint = endpoint
        self.data = data

    def __repr__(self):
        return u"%s: id=<%s> endpoint=<%s> data=<%s>" % (
            self.__class__.__name__, self.id, self.endpoint, self.data
        )

    def __unicode__(self):
        packet = u"%s:%s:%s" % (self.type, self.id, self.endpoint)
        if self.data is not None:
            packet += u":" + self.data
        return packet


class DisconnectPacket(SocketIOPacket):
    type = "0"


class ConnectPacket(SocketIOPacket):
    type = "1"


class HeartbeatPacket(SocketIOPacket):
    type = "2"


class MessagePacket(SocketIOPacket):
    type = "3"


class JSONMessagePacket(SocketIOPacket):
    type = "4"

    def __init__(self, id="", endpoint="", data=None, payload=None):
        if payload is None:
            payload = json.loads(data)
        if data is None:
            data = json.dumps(payload)
        super(JSONMessagePacket, self).__init__(id, endpoint, data)
        self.payload = payload


class EventPacket(SocketIOPacket):
    type = "5"

    def __init__(self, id="", endpoint="", data=None, name=None, args=None):
        if name is None:
            d = json.loads(data)
            name = d["name"]
            args = d["args"]
        if data is None:
            d = {"name": name, "args": args}
            data = json.dumps(d)
        super(EventPacket, self).__init__(id, endpoint, data)
        self.name, self.args = name, args

    def __repr__(self):
        return u"%s: id=<%s> endpoint=<%s> name=<%s> args=<%s>" % (
            self.__class__.__name__, self.id, self.endpoint,
            self.name, self.args
        )


class ACKPacket(SocketIOPacket):
    type = "6"


class ErrorPacket(SocketIOPacket):
    type = "7"

    def __init__(
        self, id="", endpoint="", data=None, reason=None, advice=None
    ):
        if reason is None:
            reason, advice = data.split("+", 1)
        if data is None:
            data = u"%s:%s" % (reason, advice)
        super(ErrorPacket, self).__init__(id, endpoint, data)
        self.reason, self.advice = reason, advice

    def __repr__(self):
        return u"%s: id=<%s> endpoint=<%s> reason=<%s> advice=<%s:%s>" % (
            self.__class__.__name__, self.id, self.endpoint,
            self.reason, self.advice
        )


class NoopPacket(SocketIOPacket):
    type = "8"


def parse_message(raw):
    parts = raw.split(":", 3)
    type = parts[0]
    id = parts[1]
    endpoint = parts[2]
    if len(parts) == 4:
        data = parts[3]
    else:
        data = None
    return {
        "0": DisconnectPacket, "1": ConnectPacket, "2": HeartbeatPacket,
        "3": MessagePacket, "4": JSONMessagePacket, "5": EventPacket,
        "6": ACKPacket, "7": ErrorPacket, "8": NoopPacket,
    }[type](id, endpoint, data)


class SocketIOClient(amitu.websocket_client.WebSocket):
    def __init__(self, server, port, protocol="ws", *args, **kw):
        self.server = server
        self.port = port
        self.args = args
        self.kw = kw
        self.protocol = protocol
        self.handlers = {}

    def run(self):
        conn = httplib.HTTPConnection(self.server + ":" + str(self.port))
        conn.request('GET', '/socket.io/1/')
        r = conn.getresponse().read()
        hskey = r.split(":")[0]

        super(SocketIOClient, self).__init__(
            '%s://%s:%s/socket.io/1/websocket/%s' % (
                self.protocol, self.server, self.port, hskey
            ), *self.args, **self.kw
        )
        super(SocketIOClient, self).run()

    def on(self, name, callback):
        self.handlers.setdefault(name, []).append(callback)

    def fire(self, name, *args, **kw):
        for callback in self.handlers.get(name, []):
            callback(*args, **kw)

    def emit(self, name, args):
        self.send(EventPacket(name=name, args=[args]))

    def onopen(self):
        self.fire("connect")

    def onmessage(self, msg):
        self.fire("message", msg)
        packet = parse_message(msg)
        if isinstance(packet, HeartbeatPacket):
            self.send(HeartbeatPacket())
        if isinstance(packet, EventPacket):
            self.fire(packet.name, packet.args[0])

    def ontimeout(self):
        handlers = self.handlers.get("timeout")
        if handlers:
            for handler in handlers:
                handler()
        else:
            self.sock.close()
            exit(1)


class ThreadedSocketIOClient(SocketIOClient):
    """The upstream amitu socket client can only send one message,
    and then shuts down the connection.

    This threaded client can handle a sequential conversation consisting
    of multiple messages.

    Example usage:

    rcvd = []
    def myfunc(msg):
        rcvd.append(msg)
        # do something more useful

    sockio = ThreadedSocketIOClient(server, port)
    # first message
    socketio('5:::{"foo":"bar"}', myfunc)
    # second message
    socketio('5:::{"bar":"baz"}', myfunc)

    # wait for callbacks
    while len(rcvd) < 2:
        time.sleep(1)

    # shutdown
    sockio.close()
    """

    def __init__(self, server, port, protocol="ws", *args, **kwargs):
        self._q = Queue()
        self.msg = None
        self._callback = None
        self._t = None
        super(ThreadedSocketIOClient, self
              ).__init__(server, port, protocol, *args, **kwargs)

    def __call__(self, msg, callback):
        logger.debug("%s.__call__::%s, %s",
                     self.__class__.__name__, msg, callback)
        self._q.put((msg, callback))
        if self._t is None:
            self.runloop()

    def callback(self, msg):
        logger.debug("%s.callback::calling %s with msg=%s",
                     self.__class__.__name__, self._callback, msg)
        if self._callback is not None:
            self._callback(msg)
            # re-loop
            self.runloop()
        else:
            raise AttributeError("No callback to handle message::%s" % msg)

    def runloop(self):
        logger.debug("%s.runloop",
                     self.__class__.__name__)
        # blocks until next message or terminator
        self.msg, self._callback = self._q.get()
        logger.debug("%s.runloop::callback set to %s",
                     self.__class__.__name__, self._callback)
        # initial loop
        if self._t is None:
            self._t = threading.Thread(target=self._run)
            self._t.start()
        # terminator
        elif self.msg is None:
            self._close()
        else:
            self.send_message(self.msg)

    def _run(self):
        self.on("connect", self.my_connect)
        self.on("message", self.my_message)
        self.on("disconnect", self.my_disconnect)
        self.on("error", self.my_error)
        self.on("timeout", self.my_timeout)
        # fixes connection reset by peer errors
        time.sleep(0.001)
        self.run()

    def my_error(self, error):
        self.my_disconnect('dikke error %s ik kap ermee ait' % error)

    def my_timeout(self):
        self.my_disconnect('timeout yo, ik kap ermee')

    def my_connect(self):
        self.send_message(self.msg)

    def send_message(self, msg):
        logger.debug("%s.send_message::%s",
                     self.__class__.__name__, msg)
        self.send(msg)

    def my_message(self, msg):
        logger.debug("%s.my_message::> %s",
                     self.__class__.__name__, msg)
        message = msg.split(':')
        if message[0] == "5":
            my_msg = json.loads(':'.join(message[3:]))
            self.callback(my_msg)

    def my_disconnect(self, msg=None):
        self.close()

    def close(self):
        logger.debug("%s.close",
                     self.__class__.__name__)
        self._q.put((None, None))

    def _close(self):
        self.sock.settimeout(1)
        self.sock.shutdown(socket.SHUT_RDWR)
        # no sys.exit!

    def on_server(data):
        pass

    def onclose(self):
        logger.debug("%s.onclose" %
                     (self.__class__.__name__))
        super(ThreadedSocketIOClient, self).onclose()
