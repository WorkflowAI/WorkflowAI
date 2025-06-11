# Plan to Deprecate `agent_uid`

We want to rename the `agent_uid` field returned by `/v1/{tenant}/agents/stats` to `agent_id`.

## Steps
1. **API Change**
   - Introduce a new field `agent_id` (string) in the `AgentStat` response model.
   - Continue returning `agent_uid` but mark it as deprecated in the OpenAPI schema.
2. **Client Update**
   - Update types and stores to read `agent_id` when present and fall back to `agent_uid` for backward compatibility.
3. **Deprecation Notice**
   - Communicate the deprecation in the release notes and documentation.
   - After a grace period, remove `agent_uid` from the response and client code.
