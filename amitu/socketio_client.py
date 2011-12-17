import amitu.websocket_client, httplib

class SocketIOMessage(object):
    Disconnect = "0"
    Connect = "1"
    Heartbeat = "2"
    Message = "3"
    JSONMessage = "4"
    Event = "5"
    ACK = "6"
    Error = "7"
    Noop = "8"

    def __init__(self, raw):
        parts = raw.split(":", 3)
        self.type = parts[0]
        self.id = parts[1]
        self.endpoint = parts[2]
        if len(parts) == 4:
            self.data = parts[3]
        else:
            self.data = None

    def type2name(self):
        for k, v in SocketIOMessage.__dict__.items():
            if v == self.type: return k
        raise TypeError("Unknown type: %s" % self.type)

    def __unicode__(self):
        return u"%s id=<%s> endpoint=<%s> data=<%s>" % (
            self.type2name(), self.id, self.endpoint, self.data
        )

    def __repr__(self):
        return u"<SocketIOMessage: %s>" % self

class SocketIOClient(amitu.websocket_client.WebSocket):
    def __init__(self, server, port, protocol="ws", *args, **kw):
        self.server = server
        self.port = port
        self.args = args
        self.kw = kw
        self.protocol = protocol

    def run(self):
        conn  = httplib.HTTPConnection(self.server + ":" + str(self.port))
        conn.request('POST','/socket.io/1/')
        hskey  = conn.getresponse().read().split(":")[0]

        super(SocketIOClient, self).__init__(
            '%s://%s:%s/socket.io/1/websocket/%s' % (
                self.protocol, self.server, self.port, hskey
            )
        )
        super(SocketIOClient, self).run()

    def on(self, p): pass
    def emit(self, p, q): pass

    def onopen(self):
        print("opened!")
        self.send('5:::{"name":"browser","args":["hammerlib:get_clientid:user_anon\u000d\u000a"]}')

    def onmessage(self, msg):
        print "onmessage:", SocketIOMessage(msg)

    def onclose(self):
        print "onclose"

    def ontimeout(self): pass
