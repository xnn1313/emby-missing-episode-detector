import unittest

from app.tmdb_client import TMDBClient


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class FakeHTTPClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, path, params=None, headers=None):
        self.calls.append(
            {
                "path": path,
                "params": dict(params or {}),
                "headers": dict(headers or {}),
            }
        )
        return self.responses.pop(0)

    def close(self):
        return None


class TMDBClientTests(unittest.TestCase):
    def test_search_uses_api_key_query_param_for_legacy_key(self):
        client = TMDBClient("legacy-v3-key")
        client.client.close()
        client.client = FakeHTTPClient(
            [FakeResponse(200, {"results": [{"id": 1, "name": "黑镜"}]})]
        )

        results = client.search_tv_series_candidates("黑镜")

        self.assertEqual(1, len(results))
        self.assertEqual("legacy-v3-key", client.client.calls[0]["params"]["api_key"])
        self.assertNotIn("Authorization", client.client.calls[0]["headers"])

    def test_search_retries_with_bearer_after_api_key_auth_failure(self):
        client = TMDBClient("legacy-v3-key")
        client.client.close()
        client.client = FakeHTTPClient(
            [
                FakeResponse(401, text='{"status_message":"Invalid API key"}'),
                FakeResponse(200, {"results": [{"id": 1, "name": "黑镜"}]}),
            ]
        )

        results = client.search_tv_series_candidates("黑镜")

        self.assertEqual(1, len(results))
        self.assertEqual(2, len(client.client.calls))
        self.assertEqual("legacy-v3-key", client.client.calls[0]["params"]["api_key"])
        self.assertEqual(
            "Bearer legacy-v3-key",
            client.client.calls[1]["headers"]["Authorization"],
        )


if __name__ == "__main__":
    unittest.main()
