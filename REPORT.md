# Agent UID Usage Report

This report summarizes where the `agent_uid` field is exposed in the public API.

## Endpoints

- **GET `/v1/{tenant}/agents/stats`** – defined in `api/api/routers/agents_v1.py`. The endpoint returns a page of `AgentStat` objects which contain `agent_uid`.

  ```python
  class AgentStat(BaseModel):
      agent_uid: int
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

- `client/src/types/workflowAI/models.ts` defines the `AgentStat` type with `agent_uid`.
- `client/src/store/agents.ts` stores returned stats by `agent_uid`.

These usages rely on the field name returned by the endpoint.
