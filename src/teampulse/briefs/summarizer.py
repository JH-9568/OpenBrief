from collections.abc import Sequence

from teampulse.models import ClaimStatus, SourceItem, SourceItemKind
from teampulse.schemas import BriefClaim, BriefContent, BriefSection

SECTION_TITLES = {
    "direction": "Project direction",
    "design_changes": "Design changes",
    "decisions": "Decisions",
    "planning": "Planning",
    "tasks": "Tasks",
    "completed": "Completed work",
    "schedule_risks": "Schedule and delay risks",
    "conflicts": "Conflicts and open questions",
}


class StructuredBriefBuilder:
    """Deterministic fallback until a production LLM provider is selected."""

    def build(self, source_items: Sequence[SourceItem]) -> BriefContent:
        buckets: dict[str, list[BriefClaim]] = {key: [] for key in SECTION_TITLES}
        for item in source_items:
            status = self._claim_status(item)
            claim = BriefClaim(
                text=self._claim_text(item),
                status=status,
                source_item_ids=[str(item.id)],
            )
            buckets[self._section_key(item)].append(claim)

        sections = [
            BriefSection(key=key, title=title, claims=buckets[key])
            for key, title in SECTION_TITLES.items()
        ]
        return BriefContent(
            sections=sections,
            source_window={
                "source_item_count": len(source_items),
                "builder": "deterministic-fallback",
            },
            diff_from_last_confirmed=[],
        )

    def _section_key(self, item: SourceItem) -> str:
        if item.kind in {SourceItemKind.DESIGN_UPDATE, SourceItemKind.DESIGN_COMMENT}:
            return "design_changes"
        if item.kind == SourceItemKind.PLANNING_DOC:
            return "planning"
        if item.kind == SourceItemKind.TASK_CHANGE:
            return "tasks"
        if item.kind == SourceItemKind.MEETING_MESSAGE:
            lowered = f"{item.title}\n{item.body}".lower()
            if any(token in lowered for token in ["decision", "decided", "결정"]):
                return "decisions"
            if any(token in lowered for token in ["blocker", "blocked", "지연", "막힘"]):
                return "schedule_risks"
        return "conflicts"

    def _claim_text(self, item: SourceItem) -> str:
        body = item.body.strip()
        if body:
            return f"{item.title}: {body[:500]}"
        return item.title

    def _claim_status(self, item: SourceItem) -> ClaimStatus:
        lowered = f"{item.title}\n{item.body}".lower()
        if any(token in lowered for token in ["conflict", "contradict", "충돌"]):
            return ClaimStatus.CONFLICT
        if any(token in lowered for token in ["?", "확인 필요", "needs confirmation"]):
            return ClaimStatus.NEEDS_CONFIRMATION
        if item.kind in {SourceItemKind.MEETING_MESSAGE, SourceItemKind.DESIGN_COMMENT}:
            return ClaimStatus.AI_INFERENCE
        return ClaimStatus.CONFIRMED
