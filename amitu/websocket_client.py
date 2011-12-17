import ssl, socket, urlparse
from mimetools import Message
from StringIO import StringIO

FRAME_START = "\x00"
FRAME_END = "\xff"

class WebSocketError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self): return str(self.value)


class WebSocket(object):
    def __init__(
        self, url, ca_certs=None, cert_reqs=ssl.CERT_NONE, headers=None, 
        protocol=None
    ):
        self.url = url
        self.ca_certs = ca_certs
        self.cert_reqs = cert_reqs
        self.headers = headers or {}
        self.protocol = protocol

    def _connect_and_send_handshake(self):
        params = urlparse.urlparse(self.url)
        host = params.hostname
        if params.port: host = "%s:%s" % (host, params.port)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if params.scheme == "wss":
            self.sock = ssl.wrap_socket(
                self.sock, ca_certs=self.ca_certs, cert_reqs=self.cert_reqs
            )
            port = params.port or 443
            origin = "https://%s" % host
        else:
            port = params.port or 80
            origin = "http://%s" % host

        if params.query:
            path = u"%s?%s" % (params.path, params.query)
        else:
            path = params.path

        self.headers["Upgrade"] = "WebSocket"
        self.headers["Connection"] = "Upgrade"
        self.headers["Host"] = host
        self.headers["Origin"] = origin

        if self.protocol:
            self.headers["Sec-WebSocket-Protocol"] = self.protocol

        self.sock.connect((params.hostname, params.port))

        self.sock.send(
            (
                u"GET %s HTTP/1.1\r\n%s\r\n\r\n" % (
                    path, u"\r\n".join(
                        [
                            u"%s: %s" % (k, self.headers[k])
                            for k in self.headers.keys()
                        ]
                    )
                )
            ).encode("utf-8")
        )

    def _receive_handshake(self):
        while True:
            buf = self.sock.recv(2048)
            if "\r\n\r\n" in buf: break

        headers, buf = buf.split("\r\n\r\n", 1)
        status_line, headers = headers.split("\r\n", 1)

        headers = Message(StringIO(headers))

        if (
            status_line != 'HTTP/1.1 101 Web Socket Protocol Handshake'
            or headers.get('Connection') != 'Upgrade'
            or headers.get('Upgrade') != 'WebSocket'
        ):
            raise WebSocketError('Invalid handshake')

        return buf

    def _consume_frames(self, buf):
        while FRAME_END in buf:
            frame, buf = buf.split(FRAME_END, 1)
            if frame[0] != FRAME_START: raise WebSocketError("Invalid frame")
            self.onmessage(frame[1:])
        return buf

    def run(self):
        self._connect_and_send_handshake()
        buf = self._receive_handshake()

        self.onopen()

        while True:
            buf = self._consume_frames(buf)
            res = self.sock.recv(2048)

            if not res: return self.onclose()

            buf += res

    def send(self, data):
        self.sock.send('\x00' + data.encode("utf-8") + '\xff')

    def onopen(self): pass
    def onmessage(self, message): pass
    def onclose(self): pass
    def onerror(self, error): pass
