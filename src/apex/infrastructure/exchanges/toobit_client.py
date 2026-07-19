"""Toobit Exchange API Client - Low-level HTTP communication."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
import socket
import logging
from typing import Any
import urllib.parse

import aiohttp

log = logging.getLogger(__name__)

class ToobitClientError(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(f"[{code}] {msg}")

class ToobitClient:
    BASE_URL = "https://api.toobit.com"

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            resolver = aiohttp.resolver.ThreadedResolver()
            connector = aiohttp.TCPConnector(family=socket.AF_INET, resolver=resolver)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    def _generate_signature(self, query_string: str, request_body: str = "") -> str:
        total_payload = query_string + request_body
        secret_bytes = self.api_secret.encode('utf-8')
        payload_bytes = total_payload.encode('utf-8')
        return hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()

    def _build_query_string(self, params: dict[str, Any]) -> str:
        filtered_params = {k: v for k, v in params.items() if v is not None}
        return urllib.parse.urlencode(filtered_params)

    async def _request(self, method: str, path: str, params: dict[str, Any] = None, body: dict[str, Any] = None, signed: bool = True) -> dict[str, Any] | list:
        params = params or {}
        body = body or {}
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = 10000

        query_string = self._build_query_string(params)
        request_body_str = self._build_query_string(body) if body else ""
        url = f"{self.BASE_URL}{path}"
        headers = {}
        
        if signed:
            if not self.api_key or not self.api_secret:
                raise ValueError("API Key and Secret are required")
            signature = self._generate_signature(query_string, request_body_str)
            headers["X-BB-APIKEY"] = self.api_key
            url = f"{url}?{query_string}&signature={signature}"
        else:
            if query_string: url = f"{url}?{query_string}"

        session = await self._get_session()
        try:
            async with session.request(method, url, data=request_body_str, headers=headers) as response:
                data = await response.json()
                if isinstance(data, dict) and "code" in data and data["code"] != 200:
                    raise ToobitClientError(data["code"], data.get("msg", "Unknown Error"))
                return data
        except aiohttp.ClientError as e:
            raise ToobitClientError(-1000, f"Network Error: {str(e)}")

    async def get_top_volume_symbols(self, limit: int = 10) -> list[str]:
        return [
            "BTC-SWAP-USDT", "ETH-SWAP-USDT", "SOL-SWAP-USDT", "BNB-SWAP-USDT", 
            "XRP-SWAP-USDT", "DOGE-SWAP-USDT", "ADA-SWAP-USDT", "AVAX-SWAP-USDT", 
            "LINK-SWAP-USDT", "DOT-SWAP-USDT"
        ][:limit]

    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 50) -> list:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        return await self._request("GET", "/quote/v1/klines", params=params, signed=False)

    async def get_all_klines(self, symbol: str, interval: str = "1m") -> list:
        """Fetch ALL available candles via robust pagination."""
        all_klines = []
        end_time = int(time.time() * 1000)
        while True:
            params = {"symbol": symbol, "interval": interval, "limit": 1000, "endTime": end_time}
            try:
                klines = await self._request("GET", "/quote/v1/klines", params=params, signed=False)
            except Exception as e:
                log.warning(f"Pagination stopped for {symbol} {interval}: {e}")
                break
            
            if not klines or len(klines) == 0:
                break
                
            all_klines = klines + all_klines
            
            if len(klines) < 1000:
                break
                
            end_time = klines[0][0] - 1
            await asyncio.sleep(0.2)  # Prevent rate limit
            
        return all_klines

    async def place_futures_order(self, **params: Any) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/futures/order", body=params)

    async def cancel_futures_order(self, symbol: str, order_id: str) -> dict[str, Any]:
        params = {"symbol": symbol, "orderId": order_id}
        return await self._request("DELETE", "/api/v1/futures/order", params=params)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
