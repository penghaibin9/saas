"""Real dependency regressions for the 2026-10-01 image remediation."""
import http.client
import io
import json
from pathlib import Path
import unittest

import jwt
from urllib3.exceptions import ProtocolError
from urllib3.response import HTTPResponse


class ImageDependencyUpgradeTests(unittest.TestCase):
    def test_freezes_and_policy_keep_security_floors(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('requirements.txt', 'requirements.lock'):
            text = (root / name).read_text(encoding='utf-8')
            self.assertIn('PyJWT==2.14.0', text)
            self.assertIn('urllib3==2.8.0', text)
        policy = (root / 'requirements.in').read_text(encoding='utf-8')
        self.assertIn('PyJWT>=2.14.0,<3.0', policy)
        self.assertIn('urllib3>=2.8.0,<3.0', policy)

    def test_hmac_rejects_jwks_and_array_keys_but_accepts_secret(self):
        key = {'kty': 'RSA', 'n': 'AQAB', 'e': 'AQAB'}
        for material in (json.dumps({'keys': [key]}), json.dumps([key])):
            with self.subTest(material=material):
                with self.assertRaises(jwt.InvalidKeyError):
                    jwt.encode({'userId': 'test-only'}, material, algorithm='HS256')
        secret = 'synthetic-regression-secret-32-bytes'
        token = jwt.encode({'userId': 'test-only', 'exp': 4102444800}, secret, algorithm='HS256')
        self.assertEqual(jwt.decode(token, secret, algorithms=['HS256'])['userId'], 'test-only')
        with self.assertRaises(jwt.InvalidSignatureError):
            jwt.decode(token, secret + '-wrong', algorithms=['HS256'])

    def test_chunk_size_line_is_bounded_and_normal_stream_still_works(self):
        class Socket:
            def __init__(self, data):
                self.data = io.BytesIO(data)

            def makefile(self, *args, **kwargs):
                return self.data

        def response(body):
            raw = http.client.HTTPResponse(Socket(
                b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n' + body), method='GET')
            raw.begin()
            return HTTPResponse(body=raw, headers=dict(raw.headers), original_response=raw,
                                preload_content=False)

        with self.assertRaises(ProtocolError):
            list(response(b'1;' + b'x' * 65536 + b'\r\na\r\n0\r\n\r\n').read_chunked())
        self.assertEqual(b''.join(response(b'2\r\nok\r\n0\r\n\r\n').read_chunked()), b'ok')


if __name__ == '__main__':
    unittest.main()
