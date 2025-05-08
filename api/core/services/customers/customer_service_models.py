from datetime import date
from typing import NamedTuple

from pydantic import BaseModel


class DailyUserDigest(NamedTuple):
    for_date: date
    tenant_slug: str
    org_id: str | None
    remaining_credits_usd: float
    added_credits_usd: float

    class Agent(NamedTuple):
        name: str
        agent_id: str
        agent_schema_id: int
        description: str | None
        run_count_last_24h: int
        active_run_count_last_24h: int

    agents: list[Agent]


class DailyDigestAndEmail(NamedTuple):
    daily_digest: DailyUserDigest

    class Email(NamedTuple):
        subject: str | None = None
        body: str | None = None

    email: Email


class AgentStat(BaseModel):
    run_count: int
    total_cost_usd: float

    def __str__(self) -> str:
        if self.run_count == 0 and self.total_cost_usd == 0:
            # Display a dash for empty stats to keep the table concise.
            return "-"

        return f"{self.run_count} (${round(self.total_cost_usd, 2)})"


class ActiveRunsReport(BaseModel):
    class Week(BaseModel):
        start_of_week: date
        end_of_week: date

    weeks: list[Week]

    stats: dict[str, list[AgentStat]]
