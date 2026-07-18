import httpx

from teampulse.config import Settings, get_settings
from teampulse.main import create_app


async def test_discord_setup_returns_install_url_when_application_id_is_configured():
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(discord_application_id="123")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/integration-setup/discord")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "discord"
    assert "client_id=123" in payload["install_url"]
    assert "READ_MESSAGE_HISTORY" in payload["required_permissions"]


async def test_github_setup_returns_required_permissions():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/integration-setup/github")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "github"
    assert "repository" in payload["required_config"]


async def test_unknown_setup_provider_returns_not_found():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/integration-setup/slack")

    assert response.status_code == 404
