from datetime import date

from pydantic import BaseModel


class DailyUserDigest(BaseModel):
    for_date: date
    tenant_slug: str
    org_id: str | None
    remaining_credits_usd: float
    added_credits_usd: float

    class Agent(BaseModel):
        name: str
        agent_id: str
        agent_schema_id: int
        description: str | None
        run_count_last_24h: int
        active_run_count_last_24h: int

    agents: list[Agent]


class DailyDigestAndEmail(BaseModel):
    daily_digest: DailyUserDigest

    class Email(BaseModel):
        subject: str | None = None
        body: str | None = None

    email: Email
