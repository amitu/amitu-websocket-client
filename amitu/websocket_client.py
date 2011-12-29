import ssl, socket, urlparse
from mimetools import Message
from StringIO import StringIO

import random

FRAME_START = "\x00"
FRAME_END = "\xff"


class WebSocketError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self): return str(self.value)


class WebSocket(object):

    def __init__(
        self, url, ca_certs=None, cert_reqs=ssl.CERT_NONE, headers=None,
        protocol=None, timeout=None
    ):
        self.url = url
        self.ca_certs = ca_certs
        self.cert_reqs = cert_reqs
        self.headers = headers or {}
        self.protocol = protocol
        self.timeout = timeout

    def _connect_and_send_handshake(self):

        def _generate_sec_websocket_key():
            # see http://code.google.com/p/pywebsocket/source/browse/trunk/src/example/echo_client.py
            # 4.1 16. let /spaces_n/ be a random integer from 1 to 12 inclusive.
            spaces = random.randint(1, 12)
            # 4.1 17. let /max_n/ be the largest integer not greater than
            #  4,294,967,295 divided by /spaces_n/.
            maxnum = 4294967295 / spaces
            # 4.1 18. let /number_n/ be a random integer from 0 to /max_n/
            # inclusive.
            number = random.randint(0, maxnum)
            # 4.1 19. let /product_n/ be the result of multiplying /number_n/ and
            # /spaces_n/ together.
            product = number * spaces
            # 4.1 20. let /key_n/ be a string consisting of /product_n/, expressed
            # in base ten using the numerals in the range U+0030 DIGIT ZERO (0) to
            # U+0039 DIGIT NINE (9).
            key = str(product)
            # 4.1 21. insert between one and twelve random characters from the
            # range U+0021 to U+002F and U+003A to U+007E into /key_n/ at random
            # positions.
            available_chars = range(0x21, 0x2f + 1) + range(0x3a, 0x7e + 1)
            n = random.randint(1, 12)
            for _ in xrange(n):
                ch = random.choice(available_chars)
                pos = random.randint(0, len(key))
                key = key[0:pos] + chr(ch) + key[pos:]
            # 4.1 22. insert /spaces_n/ U+0020 SPACE characters into /key_n/ at
            # random positions other than start or end of the string.
            for _ in xrange(spaces):
                pos = random.randint(1, len(key) - 1)
                key = key[0:pos] + ' ' + key[pos:]
            return number, key

        def _generate_key3():
            # http://code.google.com/p/pywebsocket/source/browse/trunk/src/example/echo_client.py
            # 4.1 26. let /key3/ be a string consisting of eight random bytes (or
            # equivalently, a random 64 bit integer encoded in a big-endian order).
            return ''.join([chr(random.randint(30, 70)) for _ in xrange(8)])

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

        _key1, key1 = _generate_sec_websocket_key()
        _key2, key2 = _generate_sec_websocket_key()


        self.headers["Upgrade"] = "WebSocket"
        self.headers["Connection"] = "Upgrade"
        self.headers["Host"] = host
        self.headers["Origin"] = origin
        self.headers["Sec-Websocket-Key1"] = key1
        self.headers["Sec-Websocket-Key2"] = key2
        key_3 = _generate_key3()
        if self.protocol:
            self.headers["Sec-WebSocket-Protocol"] = self.protocol

        self.sock.connect((params.hostname, params.port))
        self.sock.settimeout(self.timeout)

        self.sock.send((
                u"GET %s HTTP/1.1\r\n%s\r\n\r\n%s" % (
                    path, u"\r\n".join(
                        [
                            u"%s: %s" % (k, self.headers[k])
                            for k in self.headers.keys()
                        ]
                    ), key_3
                )
            ).encode("utf-8")
        )

    def _receive_handshake(self):
        while True:
            buf = self.sock.recv(2048)
            if "\r\n\r\n" in buf: break

        headers, buf = buf.split("\r\n\r\n", 1)
        status_line, headers = headers.split("\r\n", 1)

        print "BUF %s" % buf

        headers = Message(StringIO(headers))
        if (
            status_line != 'HTTP/1.1 101 WebSocket Protocol Handshake'
            or headers.get('Connection') != 'Upgrade'
            or headers.get('Upgrade') != 'WebSocket'
        ):
            raise WebSocketError('Invalid handshake')

        if len(buf) == 0:
            challenge = self.sock.recv(16)
            print "challenge %s" % challenge
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

            try:
                res = self.sock.recv(2048)
            except socket.timeout:
                self.ontimeout()
            else:
                if not res: return self.onclose()
                buf += res

    def send(self, data):
        self.sock.send('\x00' + unicode(data).encode("utf-8") + '\xff')

    def onopen(self): pass
    def onmessage(self, message): pass
    def onclose(self): pass
    def onerror(self, error): pass
    def ontimeout(self): pass
