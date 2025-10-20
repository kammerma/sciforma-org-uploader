
from __future__ import annotations
import time
from typing import Any, Dict, Optional
import httpx

class SciformaClient:
    def __init__(self, base_url: str, token_url: str, client_id: str, client_secret: str, scope: str, *,
                 timeout: int = 30, debug: bool = False, rate_limit_rps: float | None = None,
                 max_retries: int = 3, backoff_factor: float = 0.5, max_backoff: float = 60.0):
        self.base_url = base_url.rstrip('/')
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
    self.timeout = timeout
        self.debug = debug
    # Retry/backoff settings
    self.max_retries = max_retries
    self.backoff_factor = backoff_factor
    self.max_backoff = max_backoff
        self._token: Optional[str] = None
        self._token_expiry: Optional[float] = None
    # Use httpx.Timeout to allow more fine-grained control later if needed
    self._client = httpx.Client(timeout=httpx.Timeout(timeout))

        # Rate limit: min interval between requests
        self._rate_limit_rps = rate_limit_rps
        self._min_interval = (1.0 / rate_limit_rps) if (rate_limit_rps and rate_limit_rps > 0) else None
        self._last_request_ts = 0.0

    def log(self, *args):
        if self.debug:
            print("[SciformaClient]", *args)

    def _throttle(self):
        if self._min_interval is None:
            return
        now = time.time()
        wait = self._min_interval - (now - self._last_request_ts)
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.time()

    def _ensure_token(self):
        now = time.time()
        if self._token and self._token_expiry and now < self._token_expiry - 30:
            return
        self.log("Fetching OAuth2 token...")
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': self.scope,
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        # Use the resilient request helper so token fetch benefits from retries/backoff
        resp = self._request('POST', self.token_url, data=data, headers=headers, skip_auth=True)
        self.log("TOKEN RESP", resp.status_code, resp.text)
        resp.raise_for_status()
        token_json = resp.json()
        self._token = token_json.get('access_token')
        expires_in = token_json.get('expires_in', 3600)
        self._token_expiry = now + int(expires_in)

    def _should_retry_status(self, status_code: int) -> bool:
        # Retry on common transient server/network related statuses
        return status_code in (429, 500, 502, 503, 504)

    def _request(self, method: str, url: str, *, headers: Optional[Dict[str, str]] = None,
                 params: Optional[Dict[str, str]] = None, json: Any = None, data: Any = None,
                 skip_auth: bool = False) -> httpx.Response:
        """
        Centralized HTTP request with retries, exponential backoff and jitter.
        - skip_auth: if True, do not attempt to add Authorization headers or refresh token.
        """
        attempt = 0
        last_exc: Optional[BaseException] = None
        while True:
            if not skip_auth and headers is None:
                headers = self._auth_headers()

            # Ensure token (if needed) and throttle before each attempt
            if not skip_auth:
                # _auth_headers already ensures token
                pass
            self._throttle()

            try:
                resp = self._client.request(method, url, headers=headers, params=params, json=json, data=data)
                self.log(method, url, "->", resp.status_code)

                # Handle 401 specially: clear token once and retry immediately (only once)
                if resp.status_code == 401 and not skip_auth:
                    if attempt < self.max_retries:
                        self.log("401 received, clearing token and retrying auth...")
                        self._token = None
                        self._token_expiry = None
                        # ensure token on next loop by resetting headers
                        headers = None
                        attempt += 1
                        continue
                    # fall through to raise below

                # Retry on transient status codes
                if self._should_retry_status(resp.status_code) and attempt < self.max_retries:
                    backoff = min(self.max_backoff, self.backoff_factor * (2 ** attempt))
                    # add full jitter
                    jitter = backoff * 0.1
                    sleep_for = backoff + (jitter * (httpx.random.random() - 0.5) * 2)
                    self.log(f"Transient status {resp.status_code}, retrying in {sleep_for:.2f}s (attempt {attempt + 1})")
                    time.sleep(sleep_for)
                    attempt += 1
                    # clear headers so _auth_headers() is called again if necessary
                    headers = None
                    continue

                return resp

            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    backoff = min(self.max_backoff, self.backoff_factor * (2 ** attempt))
                    jitter = backoff * 0.1
                    sleep_for = backoff + (jitter * (httpx.random.random() - 0.5) * 2)
                    self.log(f"Request error: {exc!r}, retrying in {sleep_for:.2f}s (attempt {attempt + 1})")
                    time.sleep(sleep_for)
                    attempt += 1
                    # try again
                    headers = None
                    continue
                # no more retries
                raise

    def _auth_headers(self) -> Dict[str, str]:
        self._ensure_token()
        return {'Authorization': f'Bearer {self._token}'}

    def get_org_by_description(self, description: str) -> Optional[Dict[str, Any]]:
        """
        GET {baseUrl}/organizations?description=<desc>
        Accepts full object responses. Normalizes id to int if possible.
        """
        params = {'description': description}
        url = f"{self.base_url}/organizations"
        headers = self._auth_headers()
        resp = self._request('GET', url, params=params, headers=headers)
        # log body preview safely
        try:
            body_preview = resp.text[:300]
        except Exception:
            body_preview = '<non-text body>'
        self.log("GET", resp.request.url, "->", resp.status_code, body_preview)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            obj = data[0]
            if isinstance(obj, dict) and obj.get('id') is not None:
                try:
                    obj['id'] = int(obj['id'])
                except Exception:
                    pass
            return obj
        elif isinstance(data, dict) and data.get('id') is not None:
            try:
                data['id'] = int(data['id'])
            except Exception:
                pass
            return data
        return None

    def create_organization(self, *, parent_id: int, name: str, description: str) -> Dict[str, Any]:
        url = f"{self.base_url}/organizations"
        headers = self._auth_headers() | {'Content-Type': 'application/json'}
        payload = {'parent_id': parent_id, 'name': name, 'description': description, 'next_sibling_id': -10}
        resp = self._request('POST', url, headers=headers, json=payload)
        try:
            body_preview = resp.text[:300]
        except Exception:
            body_preview = '<non-text body>'
        self.log("POST", url, payload, "->", resp.status_code, body_preview)
        resp.raise_for_status()
        return resp.json()

    def patch_organization(self, org_id: int, *, parent_id: int, name: str, next_sibling_id: int, code: str) -> Dict[str, Any]:
        url = f"{self.base_url}/organizations/{org_id}"
        headers = self._auth_headers() | {'Content-Type': 'application/merge-patch+json'}
        payload = {'parent_id': parent_id, 'name': name, 'next_sibling_id': next_sibling_id, 'organization code': code, 'description': ""}
        resp = self._request('PATCH', url, headers=headers, json=payload)
        try:
            body_preview = resp.text[:300]
        except Exception:
            body_preview = '<non-text body>'
        self.log("PATCH", url, payload, "->", resp.status_code, body_preview)
        resp.raise_for_status()
        return resp.json() if resp.text else {"status": resp.status_code}
