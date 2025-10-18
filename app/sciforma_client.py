
from __future__ import annotations
import time
from typing import Any, Dict, Optional
import httpx

class SciformaClient:
    def __init__(self, base_url: str, token_url: str, client_id: str, client_secret: str, scope: str, *, timeout: int = 30, debug: bool = False):
        self.base_url = base_url.rstrip('/')
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.timeout = timeout
        self.debug = debug
        self._token: Optional[str] = None
        self._token_expiry: Optional[float] = None  # epoch seconds
        self._client = httpx.Client(timeout=timeout)

    def log(self, *args):
        if self.debug:
            print("[SciformaClient]", *args)

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
        resp = self._client.post(self.token_url, data=data, headers=headers)
        self.log("TOKEN RESP", resp.status_code, resp.text)
        resp.raise_for_status()
        token_json = resp.json()
        self._token = token_json.get('access_token')
        expires_in = token_json.get('expires_in', 3600)
        self._token_expiry = now + int(expires_in)

    def _auth_headers(self) -> Dict[str, str]:
        self._ensure_token()
        return { 'Authorization': f'Bearer {self._token}' }

    def get_org_by_description(self, description: str) -> Optional[Dict[str, Any]]:
        params = { 'description': description, 'fields': 'description' }
        url = f"{self.base_url}/organizations"
        headers = self._auth_headers()
        resp = self._client.get(url, params=params, headers=headers)
        self.log("GET", resp.request.url, "->", resp.status_code, resp.text[:300])
        if resp.status_code == 401:
            # retry once after refresh
            self._token = None; self._token_expiry = None
            headers = self._auth_headers()
            resp = self._client.get(url, params=params, headers=headers)
            self.log("GET(retry)", resp.request.url, "->", resp.status_code, resp.text[:300])
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            # assume first match is the one
            return data[0]
        elif isinstance(data, dict) and data.get('id'):
            return data
        return None

    def create_organization(self, *, parent_id: int, name: str, description: str) -> Dict[str, Any]:
        url = f"{self.base_url}/organizations"
        headers = self._auth_headers() | {'Content-Type': 'application/json'}
        payload = { 'parent_id': parent_id, 'name': name, 'description': description, 'next_sibling_id': -10 }
        resp = self._client.post(url, headers=headers, json=payload)
        self.log("POST", url, payload, "->", resp.status_code, resp.text[:300])
        if resp.status_code == 401:
            # retry once after refresh
            self._token = None; self._token_expiry = None
            headers = self._auth_headers() | {'Content-Type': 'application/json'}
            resp = self._client.post(url, headers=headers, json=payload)
            self.log("POST(retry)", url, payload, "->", resp.status_code, resp.text[:300])
        resp.raise_for_status()
        return resp.json()

    def patch_organization(self, org_id: int, *, parent_id: int, name: str, next_sibling_id: int) -> Dict[str, Any]:
        url = f"{self.base_url}/organizations/{org_id}"
        headers = self._auth_headers() | {'Content-Type': 'application/json'}
        payload = { 'parent_id': parent_id, 'name': name, 'next_sibling_id': next_sibling_id }
        resp = self._client.patch(url, headers=headers, json=payload)
        self.log("PATCH", url, payload, "->", resp.status_code, resp.text[:300])
        if resp.status_code == 401:
            # retry once after refresh
            self._token = None; self._token_expiry = None
            headers = self._auth_headers() | {'Content-Type': 'application/json'}
            resp = self._client.patch(url, headers=headers, json=payload)
            self.log("PATCH(retry)", url, payload, "->", resp.status_code, resp.text[:300])
        resp.raise_for_status()
        return resp.json() if resp.text else {"status": resp.status_code}
