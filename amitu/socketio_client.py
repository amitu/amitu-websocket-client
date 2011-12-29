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

"""
import amitu.websocket_client, httplib, json

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
        conn  = httplib.HTTPConnection(self.server + ":" + str(self.port))
        conn.request('POST','/socket.io/1/')
        r = conn.getresponse().read()
        print r
        hskey  = r.split(":")[0]

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

    def onclose(self):
        print "onclose"

    def ontimeout(self): pass
