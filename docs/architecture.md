# OpenBrief Architecture

## Product Policy

OpenBrief is a read-only local synthesis layer over project tools. The MVP collects selected Figma, Notion, Discord, and GitHub material, turns it into normalized source items, and generates grounded project briefs. Member approval exists as an advanced extension point, but the default open-source UX is a single local owner reviewing and confirming a brief.

Source systems remain authoritative. OpenBrief does not modify Figma, Notion, Discord, GitHub, or Slack in the MVP.

## Main Decisions

- Modular monolith: API, worker, and scheduler share one Python codebase.
- Provider connectors are isolated under `openbrief.connectors`.
- All provider data becomes a common `SourceItem`.
- Brief generation is separate from ingestion and confirmation.
- AI claims must carry source references and a status: confirmed, AI inference, conflict, or needs confirmation.
- Revision confirmation can snapshot active members for future team workflows. The local open-source mode creates a default owner automatically.
- Editing a brief creates a new revision hash and supersedes the previous pending draft.
- Credentials are encrypted before database storage; production key custody must use a KMS or secret manager.

## Runtime Components

```mermaid
flowchart LR
    Figma["Figma REST polling"] --> Worker["CLI / Worker"]
    Notion["Notion REST polling"] --> Worker
    GitHub["GitHub REST polling"] --> Worker
    Discord["Discord Bot REST polling"] --> Worker
    API --> DB[(PostgreSQL)]
    Worker --> DB
    Worker --> Redis[(Redis)]
    API --> Redis
    DB --> Summarizer["Brief Builder / AI Summarizer"]
    Summarizer --> DB
    Worker --> DiscordNotify["Discord daily reminder"]
```

## Ingestion Flow

1. A provider polling job receives source activity. Cloud deployments may also use webhooks.
2. Provider-specific connector verifies the request or credentials.
3. Connector normalizes data into `SourceItem`.
4. `SourceItem` is inserted idempotently by `(provider, external_id)`.
5. `openbrief sync` or a scheduled worker polls configured integrations.
6. `openbrief brief` or `openbrief sync --brief` reads source items for the project.
7. The brief builder creates a new `BriefRevision` with source citations.
8. The local owner reviews the generated brief in the dashboard.
9. Optional team approval can require all snapshotted members to approve the exact revision hash.
10. Optional notification jobs can send Discord reminders.

## Connector Notes

Figma:

- Official docs: https://developers.figma.com/docs/rest-api/webhooks/
- Relevant webhook events: `FILE_UPDATE`, `FILE_COMMENT`, `FILE_VERSION_UPDATE`.
- Webhook security uses a passcode in the payload.
- Required read scopes include `file_content:read` and `file_comments:read`; `webhooks:write` is needed to create/manage webhooks.
- Webhooks require suitable team/project/file permissions.

Notion:

- Official docs: https://developers.notion.com/reference/webhooks
- Webhook setup sends a one-time `verification_token`; subsequent events include `X-Notion-Signature`.
- The integration needs read content and read comments capabilities for selected pages/databases.
- The connection only sees resources explicitly shared with it.

Discord:

- Official docs: https://docs.discord.com/developers/resources/message
- Channel history requires `VIEW_CHANNEL` and `READ_MESSAGE_HISTORY`.
- Sending reminders requires `SEND_MESSAGES`.
- Message content can be empty unless the app is allowed to access message content under Discord's policy.
- Discord is modeled as bot REST polling plus outbound reminder messages, not as a generic incoming webhook.

## AI Boundary

The current code ships with `StructuredBriefBuilder`, a deterministic fallback that preserves the brief contract for tests and local demos. A production AI summarizer should be added behind the same boundary and must keep these guarantees:

- no claim without source IDs unless explicitly unsupported;
- all inferred claims labeled `ai_inference`;
- conflicts surfaced, not silently resolved;
- generated output stored as a reviewable revision until confirmation.

## Security and Privacy

- Source collection is opt-in per local project.
- External credentials are encrypted at rest via Fernet for local MVP.
- Production must move encryption key custody out of app environment variables.
- Discord collection needs channel/member consent and retention policy before pilot use.
- The MVP uses a temporary member-id header for confirmation; cloud/team deployments need real auth.
