# TeamPulse ERD

```mermaid
erDiagram
    WORKSPACES ||--o{ PROJECTS : owns
    PROJECTS ||--o{ PROJECT_MEMBERS : has
    PROJECTS ||--o{ INTEGRATIONS : connects
    PROJECTS ||--o{ SOURCE_ITEMS : collects
    INTEGRATIONS ||--o{ SOURCE_ITEMS : produces
    PROJECTS ||--o{ BRIEF_REVISIONS : generates
    BRIEF_REVISIONS ||--o{ BRIEF_APPROVALS : receives
    PROJECT_MEMBERS ||--o{ BRIEF_APPROVALS : grants
    BRIEF_REVISIONS ||--o{ NOTIFICATION_DELIVERIES : announces

    WORKSPACES {
        uuid id PK
        string name
        string timezone
        datetime created_at
    }

    PROJECTS {
        uuid id PK
        uuid workspace_id FK
        string name
        text description
        string daily_report_channel_id
        boolean active
        datetime created_at
    }

    PROJECT_MEMBERS {
        uuid id PK
        uuid project_id FK
        string display_name
        string email
        string role
        boolean active
        datetime created_at
    }

    INTEGRATIONS {
        uuid id PK
        uuid project_id FK
        enum provider
        string external_id
        string name
        bytes encrypted_credentials
        json config
        enum status
        datetime created_at
    }

    SOURCE_ITEMS {
        uuid id PK
        uuid project_id FK
        uuid integration_id FK
        enum provider
        string external_id
        enum kind
        string title
        text body
        text source_url
        datetime occurred_at
        datetime received_at
        json actor
        json metadata
        json raw_payload
        enum status
    }

    BRIEF_REVISIONS {
        uuid id PK
        uuid project_id FK
        int version
        string title
        string revision_hash
        enum status
        json content
        json approver_snapshot
        json source_item_ids
        string created_by
        datetime created_at
        datetime confirmed_at
    }

    BRIEF_APPROVALS {
        uuid id PK
        uuid brief_revision_id FK
        uuid project_member_id FK
        string revision_hash
        datetime approved_at
    }

    NOTIFICATION_DELIVERIES {
        uuid id PK
        uuid project_id FK
        uuid brief_revision_id FK
        string channel
        string external_channel_id
        datetime delivered_at
        json payload
    }
```

## Important Constraints

- `project_members(project_id, email)` is unique.
- `integrations(project_id, provider, external_id)` is unique.
- `source_items(provider, external_id)` is unique to avoid duplicate webhook/polling deliveries.
- `brief_revisions(project_id, revision_hash)` is unique.
- `brief_approvals(brief_revision_id, project_member_id)` is unique.
- `notification_deliveries(project_id, brief_revision_id, channel)` prevents repeated daily reminders for the same revision/channel.

## Approval Snapshot

`brief_revisions.approver_snapshot` stores the required member set at creation time. This prevents a revision's approval target from silently changing after a member is added or removed. A blocked revision should be superseded by a new revision after explicit admin action.
