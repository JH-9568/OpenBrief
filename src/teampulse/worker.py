import asyncio
import json
import uuid

from celery import Celery

from teampulse.briefs.service import build_daily_revision
from teampulse.config import get_settings
from teampulse.db import SessionFactory
from teampulse.models import Integration, Provider
from teampulse.security import CredentialCipher
from teampulse.sources.service import list_source_items

settings = get_settings()
celery_app = Celery("teampulse", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Seoul",
    task_track_started=True,
)


@celery_app.task(name="teampulse.generate_daily_brief")
def generate_daily_brief(project_id: str) -> str:
    return asyncio.run(_generate_daily_brief(uuid.UUID(project_id)))


async def _generate_daily_brief(project_id: uuid.UUID) -> str:
    async with SessionFactory() as session:
        source_items = await list_source_items(session, project_id)
        revision = await build_daily_revision(session, project_id, source_items)
        return str(revision.id)


def decrypt_integration_credentials(integration: Integration) -> dict:
    if not integration.encrypted_credentials:
        return {}
    if settings.token_encryption_key is None:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is required to decrypt integration credentials")
    cipher = CredentialCipher(settings.token_encryption_key.get_secret_value())
    return json.loads(cipher.decrypt(integration.encrypted_credentials))


@celery_app.task(name="teampulse.poll_discord_channel")
def poll_discord_channel(integration_id: str) -> int:
    # The real polling orchestration is intentionally thin here; provider permissions and
    # channel consent must be configured before this task is scheduled.
    return asyncio.run(_validate_discord_integration(uuid.UUID(integration_id)))


async def _validate_discord_integration(integration_id: uuid.UUID) -> int:
    async with SessionFactory() as session:
        integration = await session.get(Integration, integration_id)
        if integration is None or integration.provider != Provider.DISCORD:
            return 0
        decrypt_integration_credentials(integration)
        return 0
