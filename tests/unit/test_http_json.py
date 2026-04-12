from __future__ import annotations

from io import BytesIO
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from workload_analytics.clients.http_json import fetch_json_response


class FakeUrlOpenResponse:
    def __init__(
        self,
        *,
        status: int,
        payload: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._payload = payload
        self.headers = headers or {}

    def __enter__(self) -> "FakeUrlOpenResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        del exc_type, exc, traceback
        return False

    def read(self) -> bytes:
        return self._payload.encode("utf-8")


class FetchJsonResponseTest(unittest.TestCase):
    def test_dns_resolution_error_falls_back_to_curl(self) -> None:
        with (
            patch(
                "workload_analytics.clients.http_json.urlopen",
                side_effect=URLError(
                    socket.gaierror(8, "nodename nor servname provided, or not known")
                ),
            ),
            patch(
                "workload_analytics.clients.http_json.subprocess.run",
                side_effect=self._successful_curl_response,
            ),
        ):
            response = fetch_json_response(
                base_url="https://api.github.com",
                path="/orgs/openai/repos",
                params={"type": "all"},
                headers={"Accept": "application/json"},
                timeout=30,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.payload, {"items": [1, 2, 3]})
        self.assertEqual(response.headers["content-type"], "application/json")

    def test_http_error_is_returned_without_curl_fallback(self) -> None:
        error = HTTPError(
            url="https://api.github.com/repos/openai/missing",
            code=404,
            msg="Not Found",
            hdrs={"content-type": "application/json"},
            fp=BytesIO(b'{"message":"Not Found"}'),
        )
        with patch(
            "workload_analytics.clients.http_json.urlopen",
            side_effect=error,
        ):
            response = fetch_json_response(
                base_url="https://api.github.com",
                path="/repos/openai/missing",
                params={},
                headers={"Accept": "application/json"},
                timeout=30,
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.payload, {"message": "Not Found"})

    def test_curl_fallback_failure_raises_runtime_error(self) -> None:
        with (
            patch(
                "workload_analytics.clients.http_json.urlopen",
                side_effect=URLError(
                    socket.gaierror(8, "nodename nor servname provided, or not known")
                ),
            ),
            patch(
                "workload_analytics.clients.http_json.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=["curl"],
                    returncode=6,
                    stdout="",
                    stderr="Could not resolve host: api.github.com",
                ),
            ),
        ):
            with self.assertRaises(RuntimeError) as context:
                fetch_json_response(
                    base_url="https://api.github.com",
                    path="/orgs/openai/repos",
                    params={"type": "all"},
                    headers={"Accept": "application/json"},
                    timeout=30,
                )

        self.assertIn("curl fallback failed", str(context.exception))
        self.assertIn("api.github.com", str(context.exception))

    def test_curl_fallback_rejects_config_line_injection(self) -> None:
        with (
            patch(
                "workload_analytics.clients.http_json.urlopen",
                side_effect=URLError(
                    socket.gaierror(8, "nodename nor servname provided, or not known")
                ),
            ),
            patch("workload_analytics.clients.http_json.subprocess.run") as run,
        ):
            with self.assertRaises(ValueError) as context:
                fetch_json_response(
                    base_url="https://api.github.com",
                    path="/orgs/openai/repos",
                    params={"type": "all"},
                    headers={"Accept": "application/json\nurl = https://example.test"},
                    timeout=30,
                )

        self.assertIn("line breaks", str(context.exception))
        run.assert_not_called()

    @staticmethod
    def _successful_curl_response(*args, **kwargs) -> subprocess.CompletedProcess[str]:
        command = args[0]
        config = kwargs["input"]
        output_line = next(
            line for line in config.splitlines() if line.startswith('output = "')
        )
        body_path = output_line.removeprefix('output = "').removesuffix('"')
        Path(body_path).write_text('{"items":[1,2,3]}', encoding="utf-8")
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="HTTP/2 200\r\ncontent-type: application/json\r\n\r\n",
            stderr="",
        )


if __name__ == "__main__":
    unittest.main()
