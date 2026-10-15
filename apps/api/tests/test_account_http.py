"""The profile page: your name, your password, your other browsers."""

from __future__ import annotations

from httpx import AsyncClient

from archscope_api.services.auth import Principal


async def _signed_in(client: AsyncClient, email: str, password: str) -> AsyncClient:
    response = await client.post("/api/v1/auth/sign-in", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return client


async def test_profile_name_and_account_details(anon_client: AsyncClient, principal: Principal, test_password: str) -> None:
    http = await _signed_in(anon_client, principal.email, test_password)
    account = (await http.get("/api/v1/auth/account")).json()
    assert account["email"] == principal.email
    assert account["has_password"] is True
    assert account["other_sessions"] == 0

    renamed = await http.patch("/api/v1/auth/account", json={"name": "  Ana   María "})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Ana María"
    assert (await http.get("/api/v1/auth/me")).json()["name"] == "Ana María"

    blank = await http.patch("/api/v1/auth/account", json={"name": "   "})
    assert blank.status_code == 422


async def test_change_password_needs_the_current_one_and_ends_other_sessions(
    anon_client: AsyncClient, principal: Principal, test_password: str
) -> None:
    # Another browser signed in to the same account.
    other_cookie = (
        await anon_client.post("/api/v1/auth/sign-in", json={"email": principal.email, "password": test_password})
    ).cookies
    anon_client.cookies.clear()
    http = await _signed_in(anon_client, principal.email, test_password)
    assert (await http.get("/api/v1/auth/account")).json()["other_sessions"] == 1

    wrong = await http.post(
        "/api/v1/auth/account/password", json={"current_password": "nope", "new_password": "a-much-better-pass-123"}
    )
    assert wrong.status_code == 422
    weak = await http.post("/api/v1/auth/account/password", json={"current_password": test_password, "new_password": "short"})
    assert weak.status_code == 422

    changed = await http.post(
        "/api/v1/auth/account/password", json={"current_password": test_password, "new_password": "a-much-better-pass-123"}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["other_sessions"] == 0
    assert (await http.get("/api/v1/auth/me")).status_code == 200  # this browser stays signed in

    http.cookies.clear()
    http.cookies.update(other_cookie)
    assert (await http.get("/api/v1/auth/me")).status_code == 401  # the other one was signed out


async def test_sign_out_other_browsers(anon_client: AsyncClient, principal: Principal, test_password: str) -> None:
    await anon_client.post("/api/v1/auth/sign-in", json={"email": principal.email, "password": test_password})
    anon_client.cookies.clear()
    http = await _signed_in(anon_client, principal.email, test_password)
    result = await http.post("/api/v1/auth/account/sign-out-others")
    assert result.json() == {"signed_out": 1}
    assert (await http.get("/api/v1/auth/account")).json()["other_sessions"] == 0
