from datetime import UTC, datetime, timedelta

import pytest
from aioresponses import aioresponses

from pybragerone.api import BragerOneApiClient, Token

API = "https://io.brager.pl"

@pytest.mark.asyncio
async def test_initial_login_and_validate():
    client = BragerOneApiClient(API, creds_provider=lambda: ("a@b", "pw"), validate_on_start=True)

    with aioresponses() as m:
        m.post(f"{API}/v1/auth/user", payload={
            "accessToken": "T1",
            "refreshToken": "R1",
            "type": "bearer",
            "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        })
        m.get(f"{API}/v1/user", payload={"ok": True})

        tok = await client.ensure_auth()
        assert tok.access_token == "T1"

    await client.close()


@pytest.mark.asyncio
async def test_proactive_relogin_when_expiring():
    expiring = Token(
        access_token="OLD",
        expires_at=datetime.now(UTC) + timedelta(seconds=10),
    )

    loaded = [False]
    def loader():
        if not loaded[0]:
            loaded[0] = True
            return expiring
        return expiring

    client = BragerOneApiClient(API, token_loader=loader, creds_provider=lambda: ("a@b", "pw"))

    with aioresponses() as m:
        m.post(f"{API}/v1/auth/user", payload={
            "accessToken": "NEW",
            "type": "bearer",
            "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        })

        tok = await client.ensure_auth()
        assert tok.access_token == "NEW"

    await client.close()


@pytest.mark.asyncio
async def test_reactive_refresh_on_401_retry_once():
    client = BragerOneApiClient(API, creds_provider=lambda: ("a@b", "pw"))

    with aioresponses() as m:
        m.post(f"{API}/v1/auth/user", payload={
            "accessToken": "T1",
            "type": "bearer",
            "expiresAt": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
        })
        tok = await client.ensure_auth()
        assert tok.access_token == "T1"

        m.get(f"{API}/v1/user", status=401)
        m.post(f"{API}/v1/auth/user", payload={
            "accessToken": "T2",
            "type": "bearer",
            "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        })
        m.get(f"{API}/v1/user", payload={"ok": True})

        status, payload, _ = await client._req("GET", "/v1/user")
        assert status == 200
        assert payload == {"ok": True}

    await client.close()


@pytest.mark.asyncio
async def test_revoke_swallows_errors():
    client = BragerOneApiClient(API, creds_provider=lambda: ("a@b", "pw"))
    with aioresponses() as m:
        m.post(f"{API}/v1/auth/user", payload={"accessToken": "T1"})
        await client.ensure_auth()

        m.post(f"{API}/v1/auth/revoke", status=500, payload={"message": "oops"})
        await client.revoke()
        assert client._token is None

    await client.close()
