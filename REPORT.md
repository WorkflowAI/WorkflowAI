# Agent UID Usage Report

This report summarizes where the `agent_uid` field is exposed in the public API.

## Endpoints

- **GET `/v1/{tenant}/agents/stats`** – defined in `api/api/routers/agents_v1.py`. The endpoint returns a page of `AgentStat` objects which now include a string `agent_id` field while still exposing `agent_uid`.

  ```python
  class AgentStat(BaseModel):
      agent_id: str
      agent_uid: int = Field(..., deprecated=True)
      run_count: int
      total_cost_usd: float

  @router.get("/stats")
  async def get_agent_stats(...):
      ...
  ```

  Source lines: `api/api/routers/agents_v1.py` lines 143‑162.

No other FastAPI routes expose `agent_uid` in request or response payloads.

## Client Usage

The client expects this field when consuming the stats endpoint:

- `client/src/types/workflowAI/models.ts` defines the `AgentStat` type with the new `agent_id` string field and the deprecated `agent_uid`.
- `client/src/store/agents.ts` stores returned stats keyed by `agent_id` when present, falling back to `agent_uid`.

These usages rely on the field name returned by the endpoint.

## Tests

There are currently no component tests covering the `/agents/stats` endpoint. As
such, renaming `agent_uid` to `agent_id` did not trigger test failures.

To ensure the API contract is validated, a new component test should be added.
One option would be `api/tests/component/agents/stats_test.py` verifying that the
response for `GET /v1/{tenant}/agents/stats` includes both `agent_id` and the
deprecated `agent_uid` fields.
