from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import token_vault


class _Resp:
    def __init__(self, data=None):
        self.data = data


class _RpcCall:
    def __init__(self, db, name: str, params: dict):
        self.db = db
        self.name = name
        self.params = params

    def execute(self):
        user_id = self.params["p_user_id"]
        if self.name == "set_google_refresh_token":
            token = self.params["p_token"]
            self.db.profiles[user_id] = {
                "google_refresh_token": None,
                "google_refresh_token_enc": self.db.encrypt(token),
                "_google_refresh_token": token,
            }
            return _Resp()
        if self.name == "get_google_refresh_token":
            return _Resp(self.db.profiles[user_id]["_google_refresh_token"])
        if self.name == "set_api_token":
            token = self.params["p_token"]
            integration = self.params["p_integration_type"]
            self.db.user_integrations[(user_id, integration)] = {
                "api_token": None,
                "api_token_enc": self.db.encrypt(token),
                "_api_token": token,
            }
            return _Resp()
        if self.name == "get_api_token":
            integration = self.params["p_integration_type"]
            return _Resp(self.db.user_integrations[(user_id, integration)]["_api_token"])
        raise AssertionError(f"Unexpected RPC {self.name}")


class _FakeVaultDb:
    def __init__(self):
        self.profiles = {}
        self.user_integrations = {}

    def rpc(self, name: str, params: dict):
        return _RpcCall(self, name, params)

    @staticmethod
    def encrypt(token: str | None):
        if token is None:
            return None
        return f"pgcrypto-bytea::{token[::-1]}".encode()


def test_google_refresh_token_round_trips_without_plaintext_storage():
    os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-bytes"
    db = _FakeVaultDb()
    user_id = "11111111-1111-1111-1111-111111111111"

    token_vault.set_google_refresh_token(user_id, "google-refresh-secret", db)

    raw = db.profiles[user_id]
    assert raw["google_refresh_token"] is None
    assert raw["google_refresh_token_enc"] != b"google-refresh-secret"
    assert token_vault.get_google_refresh_token(user_id, db) == "google-refresh-secret"


def test_api_token_round_trips_without_plaintext_storage():
    os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-bytes"
    db = _FakeVaultDb()
    user_id = "22222222-2222-2222-2222-222222222222"

    token_vault.set_api_token(user_id, "clickup-access-secret", db)

    raw = db.user_integrations[(user_id, "clickup")]
    assert raw["api_token"] is None
    assert raw["api_token_enc"] != b"clickup-access-secret"
    assert token_vault.get_api_token(user_id, db) == "clickup-access-secret"
