import unittest


class HttpTests(unittest.TestCase):
    def test_http_error_includes_response_body(self):
        from app.http import HTTPError, SimpleResponse

        response = SimpleResponse(status_code=401, body=b'{"error":"Unauthorized"}')

        with self.assertRaises(HTTPError) as ctx:
            response.raise_for_status()

        self.assertEqual(str(ctx.exception), 'HTTP 401: {"error":"Unauthorized"}')


if __name__ == "__main__":
    unittest.main()
