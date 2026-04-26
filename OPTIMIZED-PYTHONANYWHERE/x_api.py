import base64
import hashlib
import hmac
import json
from typing import Any
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth1

from settings import Config


X_API_BASE = "https://api.x.com"


def build_crc_response_token(crc_token: str, consumer_secret: str) -> str:
    digest = hmac.new(
        consumer_secret.encode("utf-8"),
        crc_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return "sha256=" + base64.b64encode(digest).decode("utf-8")


def verify_webhook_signature(payload: bytes, signature_header: str, consumer_secret: str) -> bool:
    expected = "sha256=" + base64.b64encode(
        hmac.new(
            consumer_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return hmac.compare_digest(expected, signature_header or "")


class XApiClient:
    def __init__(self, config: Config):
        self.config = config
        self.timeout = config.x_timeout_seconds
        self._generated_bearer_token: str | None = None

    def crc_response_token(self, crc_token: str) -> str:
        if not self.config.x_api_secret:
            raise RuntimeError("X_API_SECRET is required for CRC responses")
        return build_crc_response_token(crc_token, self.config.x_api_secret)

    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> bool:
        if not self.config.x_api_secret:
            return False
        return verify_webhook_signature(payload, signature_header, self.config.x_api_secret)

    def create_reply(self, tweet_id: str, text: str) -> dict[str, Any]:
        self.config.require_reply_posting()
        payload = {
            "text": text,
            "reply": {
                "in_reply_to_tweet_id": str(tweet_id),
            },
        }
        return self._request(
            "POST",
            "/2/tweets",
            auth_mode="oauth1",
            json_body=payload,
        )

    def get_user_by_username(self, username: str) -> dict[str, Any]:
        encoded = quote(username.lstrip("@"))
        return self._request("GET", f"/2/users/by/username/{encoded}", auth_mode="bearer")

    def create_webhook(self, url: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/2/webhooks",
            auth_mode="bearer",
            json_body={"url": url},
        )

    def validate_webhook(self, webhook_id: str) -> dict[str, Any]:
        return self._request("PUT", f"/2/webhooks/{webhook_id}", auth_mode="bearer")

    def subscribe(self, webhook_id: str) -> dict[str, Any]:
        auth_mode = "oauth2user" if self.config.x_oauth2_user_token else "oauth1"
        return self._request(
            "POST",
            f"/2/account_activity/webhooks/{webhook_id}/subscriptions/all",
            auth_mode=auth_mode,
            json_body={},
        )

    def check_subscription(self, webhook_id: str) -> dict[str, Any]:
        auth_mode = "oauth2user" if self.config.x_oauth2_user_token else "oauth1"
        return self._request(
            "GET",
            f"/2/account_activity/webhooks/{webhook_id}/subscriptions/all",
            auth_mode=auth_mode,
        )

    def list_subscriptions(self, webhook_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/2/account_activity/webhooks/{webhook_id}/subscriptions/all/list",
            auth_mode="bearer",
        )

    def replay(self, webhook_id: str, from_date: str, to_date: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/2/webhooks/replay",
            auth_mode="bearer",
            json_body={
                "from_date": from_date,
                "to_date": to_date,
                "webhook_id": webhook_id,
            },
        )

    def _request(
        self,
        method: str,
        path: str,
        auth_mode: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{X_API_BASE}{path}"
        headers = {"Content-Type": "application/json"}
        auth = None
        bearer_token = None

        if auth_mode == "bearer":
            bearer_token = self._get_bearer_token()
            headers["Authorization"] = f"Bearer {bearer_token}"
        elif auth_mode == "oauth2user":
            if not self.config.x_oauth2_user_token:
                raise RuntimeError("X_OAUTH2_USER_TOKEN is required for OAuth2 user requests")
            headers["Authorization"] = f"Bearer {self.config.x_oauth2_user_token}"
        elif auth_mode == "oauth1":
            auth = OAuth1(
                self.config.x_api_key,
                self.config.x_api_secret,
                self.config.x_access_token,
                self.config.x_access_token_secret,
            )
        else:
            raise ValueError(f"Unsupported auth mode: {auth_mode}")

        response = requests.request(
            method,
            url,
            headers=headers,
            auth=auth,
            json=json_body,
            timeout=self.timeout,
        )
        if auth_mode == "bearer" and response.status_code == 401:
            refreshed_token = self._generate_app_bearer_token()
            if refreshed_token != bearer_token:
                headers["Authorization"] = f"Bearer {refreshed_token}"
                response = requests.request(
                    method,
                    url,
                    headers=headers,
                    auth=auth,
                    json=json_body,
                    timeout=self.timeout,
                )
        return self._parse_response(response)

    def _get_bearer_token(self) -> str:
        if self._generated_bearer_token:
            return self._generated_bearer_token
        if self.config.x_bearer_token:
            return self.config.x_bearer_token
        return self._generate_app_bearer_token()

    def _generate_app_bearer_token(self) -> str:
        response = requests.post(
            f"{X_API_BASE}/oauth2/token",
            auth=HTTPBasicAuth(self.config.x_api_key, self.config.x_api_secret),
            data={"grant_type": "client_credentials"},
            timeout=self.timeout,
        )
        payload = self._parse_response(response)
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("X API oauth2/token response did not include access_token")
        self._generated_bearer_token = token
        return token

    @staticmethod
    def _parse_response(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = {"raw_text": response.text}

        if response.ok:
            return payload

        detail = payload
        if isinstance(payload, dict):
            errors = payload.get("errors")
            if errors and isinstance(errors, list):
                first_error = errors[0]
                detail = first_error.get("detail") or first_error.get("title") or payload
        raise RuntimeError(f"X API request failed ({response.status_code}): {detail}")
