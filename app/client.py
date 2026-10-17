from __future__ import annotations

import logging
import time
from typing import Any

import requests

from .provinces import Province


LOG = logging.getLogger(__name__)

BASE_URL = "https://cx.sinopecsales.com"
HISTORY_URL = f"{BASE_URL}/yjkqiantai/data/initOilPrice"
SWITCH_URL = f"{BASE_URL}/yjkqiantai/data/switchProvince"


class OilPriceClient:
    def __init__(self, timeout: tuple[float, float] = (10.0, 30.0), retries: int = 3) -> None:
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/155.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": f"{BASE_URL}/yjkqiantai/core/main",
            }
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                return response
            except Exception as exc:  # noqa: BLE001 - retried below
                last_error = exc
                LOG.warning("%s %s failed (attempt %s/%s): %s", method, url, attempt, self.retries, exc)
                if attempt < self.retries:
                    time.sleep(2 * attempt)
        raise RuntimeError(f"request failed after {self.retries} attempts: {url}") from last_error

    def select_province(self, province: Province) -> dict[str, Any]:
        response = self._request(
            "POST",
            SWITCH_URL,
            json={"provinceId": str(province.code)},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        payload = response.json()
        data = payload.get("data") or {}
        check = data.get("provinceCheck") or {}
        upstream_name = str(check.get("PROVINCE_NAME") or "").strip()
        if upstream_name and upstream_name != province.name:
            LOG.warning("province name mismatch for %s: upstream=%s", province.name, upstream_name)
        return payload

    def fetch_history(self, province: Province) -> dict[str, Any]:
        self.select_province(province)
        response = self._request("GET", HISTORY_URL)
        payload = response.json()
        data = payload.get("data") or {}
        if not data.get("provinceCheck") and not data.get("provinceData") and not data.get("area"):
            raise ValueError("history response is empty; province selection was not accepted")
        return payload
