import threading, Queue
from amitu import websocket_client

class _Writer(threading.Thread):
    def __init__(self, ws):
        super(_Writer, self).__init__()
        self.daemon = True
        self.ws = ws
        self.queue = Queue.Queue()

    def send(self, data):
        self.queue.put(data)

    def run(self):
        while True:
            self.ws._send(self.queue.get(block=True))

class WebSocket(websocket_client.WebSocket):
    """
    Threaded WebSocket class

    Use this class to use a threaded websocket. It reads data from server
    on the current thread, and sends data on a separate daemon thread.

    >>> def onmessage(message): print "onmessage", message
    ...
    >>> def onopen(): print "onopen"
    ...
    >>> def onclose(): print "onclose"
    ...
    >>> ws = WebSocket("ws://server.com:8080/path")
    >>> ws.onopen(onopen)
    >>> ws.onclose(onclose)
    >>> ws.onmessage(onmessage)

    >>> ws.run() # blocks
    """
    def __init__(self, *args, **kw):
        websocket_client.WebSocket.__init__(self, *args, **kw)

        self.writer = _Writer(self)

        self.onopen_handlers = []
        self.onclose_handlers = []
        self.onmessage_handlers = []

    def run(self):
        self.writer.start()
        websocket_client.WebSocket.run(self)

    def send(self, data):
        self.writer.send(data)

    def _fire_onopen(self):
        for cb in self.onopen_handlers: cb()
    def _fire_onmessage(self, data):
        for cb in self.onmessage_handlers: cb(data)
    def _fire_onclose(self):
        for cb in self.onclose_handlers: cb()

    def onopen(self, cb): self.onopen_handlers.append(cb)
    def onmessage(self, cb): self.onmessage_handlers.append(cb)
    def onclose(self, cb): self.onclose_handlers.append(cb)

class WebSocketThreaded(WebSocket, threading.Thread):
    """
    WebSocketThreaded

    This is a thread that runs in the background, reading and writing both
    in two different threads.

    >>> def onmessage(message): print "onmessage", message
    ...
    >>> def onopen(): print "onopen"
    ...
    >>> def onclose(): print "onclose"
    ...
    >>> ws = WebSocketThreaded("ws://server.com:8080/path")
    >>> ws.onopen(onopen)
    >>> ws.onclose(onclose)
    >>> ws.onmessage(onmessage)

    >>> ws.start()
    >>> ws.wait()
    """
    def __init__(self, *args, **kw):
        WebSocket.__init__(self, *args, **kw)
        threading.Thread.__init__(self)

