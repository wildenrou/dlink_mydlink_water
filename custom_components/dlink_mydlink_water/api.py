from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse

from aiohttp import ClientSession
from yarl import URL

from .const import ANDROID_CLIENT_ID, ANDROID_PRIVILEGE_KEY, BOOTSTRAP_HOST, REDIRECT_URI


class MydlinkApiError(Exception):
    """Raised when mydlink API calls fail."""


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


@dataclass
class AuthData:
    access_token: str
    refresh_token: str | None
    api_site: str
    target_site: str | None
    expires_at: float


class MydlinkApiClient:
    """Small mydlink OpenAPI client for DCH-S162/DCH-S163 polling.

    This intentionally mirrors the Android app behavior discovered from the APK:
    - password is sent as MD5(password)
    - redirect_uri is raw/unescaped in the actual URL
    - access_token is passed as a query parameter for OpenAPI endpoints
    """

    def __init__(
        self,
        session: ClientSession,
        email: str,
        password: str,
        android_id: str,
        device_name: str,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._android_id = android_id
        self._device_name = device_name
        self._auth: AuthData | None = None

    async def async_login(self) -> AuthData:
        timestamp = str(int(time.time()))
        password_md5 = _md5(self._password)
        sig_raw = (
            f"/oauth/authorize2?client_id={ANDROID_CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&user_name={quote_plus(self._email)}"
            f"&password={password_md5}"
            f"&response_type=token"
            f"&timestamp={timestamp}"
            f"&uc_id={self._android_id}"
            f"&uc_name={quote_plus(self._device_name)}"
            f"{ANDROID_PRIVILEGE_KEY}"
        )
        sig = _md5(sig_raw)

        # redirect_uri must intentionally remain raw in the actual query string.
        raw_url = (
            f"https://{BOOTSTRAP_HOST}/oauth/authorize2"
            f"?client_id={ANDROID_CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&user_name={quote_plus(self._email)}"
            f"&password={password_md5}"
            f"&response_type=token"
            f"&timestamp={timestamp}"
            f"&uc_id={self._android_id}"
            f"&uc_name={quote_plus(self._device_name)}"
            f"&sig={sig}"
        )

        async with self._session.get(
            URL(raw_url, encoded=True),
            headers={"User-Agent": "mydlink-Android", "Accept": "*/*"},
            allow_redirects=False,
            timeout=20,
        ) as response:
            if response.status != 302:
                body = await response.text()
                raise MydlinkApiError(f"Login failed: HTTP {response.status}: {body}")

            location = response.headers.get("Location")
            if not location:
                raise MydlinkApiError("Login failed: missing redirect Location header")

        params = {k: v[0] for k, v in parse_qs(urlparse(location).query).items()}
        try:
            access_token = params["access_token"]
            api_site = params["api_site"]
        except KeyError as err:
            raise MydlinkApiError(f"Login redirect missing expected token data: {params}") from err

        expires_in = int(params.get("expires_in", "172800"))
        self._auth = AuthData(
            access_token=access_token,
            refresh_token=params.get("refresh_token"),
            api_site=api_site,
            target_site=params.get("target_site"),
            # Renew before expiry.
            expires_at=time.time() + max(expires_in - 300, 60),
        )
        return self._auth

    async def _ensure_auth(self) -> AuthData:
        if self._auth is None or time.time() >= self._auth.expires_at:
            return await self.async_login()
        return self._auth

    async def _request_json(self, method: str, path: str, *, json_body: Any | None = None) -> Any:
        auth = await self._ensure_auth()
        url = f"https://{auth.api_site}{path}?access_token={auth.access_token}"

        headers = {
            "User-Agent": "mydlink-Android",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
        }

        async with self._session.request(
            method,
            url,
            headers=headers,
            json=json_body,
            timeout=20,
        ) as response:
            text = await response.text()
            if response.status in (400, 401) and "Invalid access token" in text:
                self._auth = None
                auth = await self.async_login()
                url = f"https://{auth.api_site}{path}?access_token={auth.access_token}"
                async with self._session.request(
                    method,
                    url,
                    headers=headers,
                    json=json_body,
                    timeout=20,
                ) as retry_response:
                    retry_text = await retry_response.text()
                    if retry_response.status >= 400:
                        raise MydlinkApiError(
                            f"API failed after re-login: HTTP {retry_response.status}: {retry_text}"
                        )
                    return await retry_response.json()

            if response.status >= 400:
                raise MydlinkApiError(f"API failed: HTTP {response.status}: {text}")
            return await response.json()

    async def async_get_device_list(self) -> list[dict[str, Any]]:
        data = await self._request_json("GET", "/me/device/list")
        return list(data.get("data", []))

    async def async_get_device_info(self, mac: str, mydlink_id: str) -> dict[str, Any]:
        body = {"data": [{"mac": mac, "mydlink_id": mydlink_id}]}
        data = await self._request_json("POST", "/me/device/info", json_body=body)
        items = data.get("data", [])
        if not items:
            raise MydlinkApiError(f"No device info returned for {mydlink_id}")
        return dict(items[0])

    async def async_get_all_device_info(self) -> dict[str, Any]:
        devices = await self.async_get_device_list()
        water_devices = [d for d in devices if str(d.get("device_model", "")).startswith("DCH-S16")]
        infos: list[dict[str, Any]] = []
        for device in water_devices:
            mac = str(device.get("mac", ""))
            mydlink_id = str(device.get("mydlink_id", ""))
            if mac and mydlink_id:
                info = await self.async_get_device_info(mac, mydlink_id)
                info["_list_data"] = device
                infos.append(info)
        return {"devices": infos}


def status_value(info: dict[str, Any], uid: int, status_type: int) -> int | None:
    """Return a status value from change_cache.status_change."""
    change_cache = info.get("change_cache") or {}
    for item in change_cache.get("status_change") or []:
        metadata = item.get("metadata") or {}
        if metadata.get("uid") == uid and metadata.get("type") == status_type:
            try:
                return int(metadata.get("value"))
            except (TypeError, ValueError):
                return None
    return None
