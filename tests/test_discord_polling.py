from datetime import UTC, datetime

from teampulse.config import Settings
from teampulse.connectors.base import NormalizedSourceItem
from teampulse.integrations.discord import poll_discord_integration
from teampulse.models import Integration, Project, Provider, SourceItemKind, Workspace


class FakeDiscordClient:
    async def fetch_channel_messages(
        self,
        *,
        bot_token: str,
        project_id: str,
        integration_id: str | None,
        channel_id: str,
        after: str | None = None,
        limit: int = 50,
    ) -> list[NormalizedSourceItem]:
        assert bot_token == "test-token"
        assert channel_id == "channel-1"
        assert limit == 50
        return [
            NormalizedSourceItem(
                project_id=project_id,
                integration_id=integration_id,
                provider=Provider.DISCORD,
                external_id="discord:101",
                kind=SourceItemKind.MEETING_MESSAGE,
                title="Discord message in channel-1",
                body="결정: 첫 MVP는 Discord 수집부터 한다.",
                source_url="https://discord.com/channels/guild/channel-1/101",
                occurred_at=datetime.now(UTC),
                actor={"username": "jin"},
                metadata={"channel_id": channel_id, "message_id": "101"},
                raw_payload={"id": "101"},
            ),
            NormalizedSourceItem(
                project_id=project_id,
                integration_id=integration_id,
                provider=Provider.DISCORD,
                external_id="discord:102",
                kind=SourceItemKind.COMMAND,
                title="Discord message in channel-1",
                body="/status",
                source_url="https://discord.com/channels/guild/channel-1/102",
                occurred_at=datetime.now(UTC),
                actor={"username": "jin"},
                metadata={"channel_id": channel_id, "message_id": "102"},
                raw_payload={"id": "102"},
            ),
        ]


async def test_poll_discord_integration_stores_messages_and_checkpoint(session):
    workspace = Workspace(name="Acme")
    session.add(workspace)
    await session.flush()
    project = Project(workspace_id=workspace.id, name="Launch")
    session.add(project)
    await session.flush()
    integration = Integration(
        project_id=project.id,
        provider=Provider.DISCORD,
        external_id="channel-1",
        name="Project channel",
        config={"channel_id": "channel-1"},
    )
    session.add(integration)
    await session.commit()

    result = await poll_discord_integration(
        session,
        integration.id,
        Settings(discord_bot_token="test-token"),
        FakeDiscordClient(),
    )

    assert result.fetched == 2
    assert result.stored == 2
    assert result.duplicates == 0
    assert result.last_message_id == "102"

    await session.refresh(integration)
    assert integration.config["last_message_id"] == "102"

    duplicate_result = await poll_discord_integration(
        session,
        integration.id,
        Settings(discord_bot_token="test-token"),
        FakeDiscordClient(),
    )
    assert duplicate_result.stored == 0
    assert duplicate_result.duplicates == 2
