from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import socket
import subprocess
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class JsonHttpResponse:
    status_code: int
    payload: object
    headers: Mapping[str, str]


def fetch_json_response(
    *,
    base_url: str,
    path: str,
    params: Mapping[str, str],
    headers: Mapping[str, str],
    timeout: int,
) -> JsonHttpResponse:
    query = urlencode(sorted(params.items()))
    url = f"{base_url.rstrip('/')}{path}"
    if query:
        url = f"{url}?{query}"

    request = Request(url, headers=dict(headers), method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return JsonHttpResponse(
                status_code=response.status,
                payload=_decode_payload(response.read().decode("utf-8")),
                headers=dict(response.headers.items()),
            )
    except HTTPError as exc:
        try:
            return JsonHttpResponse(
                status_code=exc.code,
                payload=_decode_payload(exc.read().decode("utf-8")),
                headers=dict(exc.headers.items()),
            )
        finally:
            exc.close()
    except URLError as exc:
        if not _is_dns_resolution_error(exc):
            raise
        return _fetch_json_with_curl(
            url=url,
            headers=headers,
            timeout=timeout,
            original_error=exc,
        )


def _decode_payload(raw_body: str) -> object:
    try:
        return json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        return {"message": raw_body} if raw_body else {}


def _is_dns_resolution_error(error: URLError) -> bool:
    reason = getattr(error, "reason", None)
    if isinstance(reason, socket.gaierror):
        return True

    message = str(error).lower()
    return any(
        fragment in message
        for fragment in (
            "nodename nor servname provided",
            "name or service not known",
            "temporary failure in name resolution",
            "failed to resolve",
        )
    )


def _fetch_json_with_curl(
    *,
    url: str,
    headers: Mapping[str, str],
    timeout: int,
    original_error: URLError,
) -> JsonHttpResponse:
    with NamedTemporaryFile(delete=False) as body_file:
        os.fchmod(body_file.fileno(), 0o600)
        body_path = body_file.name

    try:
        command = ["curl", "-sS", "--config", "-"]
        config_lines = [
            "location",
            _format_curl_config_line("request", "GET"),
            _format_curl_config_line("dump-header", "-"),
            _format_curl_config_line("output", body_path),
            _format_curl_config_line("connect-timeout", str(timeout)),
            _format_curl_config_line("max-time", str(timeout)),
        ]
        for key, value in headers.items():
            config_lines.append(_format_curl_config_line("header", f"{key}: {value}"))
        config_lines.append(_format_curl_config_line("url", url))
        config = "\n".join(config_lines) + "\n"

        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            input=config,
            text=True,
            timeout=timeout + 5,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or f"curl exited with {completed.returncode}"
            raise RuntimeError(
                "curl fallback failed after urllib DNS resolution error for "
                f"{url!r}: {detail}"
            ) from original_error

        status_code, response_headers = _parse_curl_headers(completed.stdout)
        raw_body = Path(body_path).read_text(encoding="utf-8")
        return JsonHttpResponse(
            status_code=status_code,
            payload=_decode_payload(raw_body),
            headers=response_headers,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "curl fallback timed out after urllib DNS resolution error for "
            f"{url!r}."
        ) from exc
    finally:
        Path(body_path).unlink(missing_ok=True)


def _parse_curl_headers(raw_headers: str) -> tuple[int, dict[str, str]]:
    blocks: list[list[str]] = []
    current_block: list[str] = []

    for line in raw_headers.splitlines():
        normalized = line.rstrip("\r")
        if not normalized:
            if current_block:
                blocks.append(current_block)
                current_block = []
            continue
        current_block.append(normalized)

    if current_block:
        blocks.append(current_block)

    for block in reversed(blocks):
        status_line = block[0]
        if not status_line.startswith("HTTP/"):
            continue

        status_parts = status_line.split()
        if len(status_parts) < 2 or not status_parts[1].isdigit():
            break

        headers: dict[str, str] = {}
        for header_line in block[1:]:
            if ":" not in header_line:
                continue
            name, value = header_line.split(":", 1)
            headers[name.strip()] = value.strip()
        return int(status_parts[1]), headers

    raise RuntimeError("curl fallback returned an invalid HTTP response header block.")


def _format_curl_config_line(key: str, value: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError("curl config values must not contain line breaks.")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{key} = "{escaped}"'
