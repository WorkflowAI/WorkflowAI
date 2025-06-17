# MCP Tool Response Token Limit Issues

## Problem Statement

We're experiencing issues with MCP (Model Context Protocol) tools returning responses that exceed the maximum allowed token limit of 25,000 tokens when used through Claude code as the MCP client.

## Current Errors

### Observed Issues
- `workflowai:list_agents(from_date: "2024-12-10T00:00:00Z")`: **249,108 tokens** (10x over limit)
- `list_available_models`: **32,007 tokens** (1.3x over limit)

## Discussion Points by MCP Tool

### `list_available_models()`
- **Current Issue**: Returns 32,007 tokens - moderately over limit
- **Discussion Points**:
  - Are we returning too much metadata per model (descriptions, capabilities, pricing, etc.)?
  - Should we implement a "summary" mode that returns only essential fields (model_id, provider, basic capabilities)?
  - Could we group models by provider/category to reduce redundant information?
  - Should we have separate endpoints for model listing vs. detailed model specs?
  - Can we implement model filtering by provider, capability, or cost tier?
- **Pierre's Suggestions**:
  - Should be paginated
  - Return the models that are most used in WorkflowAI first (prioritize popular models)
  - Should also include recent models (newly added models might be interesting to users)
- **Pierre's Refined Suggestions**:
  - Should be paginated
  - Add a `sort_by` parameter to let the MCP client decide ordering:
    - `popularity` - most used models first
    - `price` - cheapest models first
    - `recent` - newly added models first  
    - `intelligence` - most capable models first
  - This gives clients control over what they prioritize while keeping responses manageable

### `list_agents(from_date)`
- **Current Issue**: Returns 249,108 tokens - extremely large response (10x over limit)
- **Discussion Points**:
  - Should we implement pagination by default with a reasonable page size (e.g., 20-50 agents)?
  - What agent fields are essential vs. optional (stats, configurations, full schemas)?
  - Could we implement a "summary" vs "detailed" response mode?
  - Should statistics be optional or computed on-demand?
  - Can we limit the date range for statistics to reduce computation and response size?
  - Should we filter out inactive/archived agents by default?
- **Pierre's Suggestions**:
  - Should be paginated
  - Return active agents first (prioritize agents that are currently being used)
  - Should also include recently created agents (new agents might need attention/debugging)
- **Pierre's Refined Suggestions**:
  - Should be paginated
  - Add a `sort_by` parameter to let the MCP client decide ordering:
    - `active` - currently active agents first
    - `runs` - agents with most runs first
    - `recently_created` - newest agents first
  - This gives clients control over what they prioritize while keeping responses manageable

### `fetch_run_details(agent_id, run_id, run_url)`
- **Potential Issues**: Could return large responses for runs with extensive input/output data
- **Discussion Points**:
  - Should we truncate large input/output data and provide "show more" functionality?
  - Can we implement field selection (sparse fieldsets) to only return requested details?
  - Should we separate run metadata from run data (input/output) into different calls?
  - Could we implement content compression for large text fields?
  - Should we provide preview vs. full content modes for task input/output?

### `get_agent_versions(task_id, version_id)`
- **Potential Issues**: Returning all versions might include large schema data
- **Discussion Points**:
  - Should we paginate version lists for agents with many versions?
  - Can we return version summaries vs. full schema data by default?
  - Should schema details be fetched separately on-demand?
  - Could we implement version filtering (e.g., only published, only recent)?
  - Should we limit the number of versions returned unless explicitly requested?

### `search_runs_by_metadata(agent_id, field_queries, limit, offset)` *(WIP - commented out)*
- **Potential Issues**: Already implements pagination but could return large run data
- **Discussion Points**:
  - Should we enforce stricter default limits (currently allows up to arbitrary numbers)?
  - Can we implement progressive loading (metadata first, then full details on request)?
  - Should we return run summaries vs. full run details in search results?
  - Could we implement field selection for returned run data?
  - Should large input/output data be truncated in search results?

### `ask_ai_engineer(agent_id, message, ...)`
- **Potential Issues**: AI responses could be very long, especially for complex queries
- **Discussion Points**:
  - Should we implement response length limits on the AI engineer responses?
  - Can we provide streaming responses for long AI engineer conversations?
  - Should we break down complex responses into multiple smaller messages?
  - Could we implement response summarization for very long responses?
  - Should we limit the context provided to the AI engineer to control response size?

### `deploy_agent_version(agent_id, version_id, environment)`
- **Low Risk**: Deployment responses are typically small (confirmation + migration guide)
- **Discussion Points**:
  - Migration guides could potentially become large - should we limit their size?
  - Could we provide basic vs. detailed migration instructions?
  - Should detailed migration examples be provided separately?

## General Solution Approaches to Discuss

### Pagination Strategies
- Cursor-based pagination for time-ordered data (runs, versions)
- Offset/limit pagination for search results
- Page size recommendations (20-50 items for lists, 10-20 for detailed items)
- Default pagination for all list operations

### Response Filtering
- Field selection (sparse fieldsets) - let clients specify which fields they need
- Response modes: "summary", "detailed", "full"
- Conditional inclusion of expensive fields (statistics, large text content)
- Client-specified response formats

### Data Structure Optimization
- Removing redundant information across items
- Using references instead of full nested objects
- Compressing common patterns
- Truncating large text fields with "show more" functionality

### Progressive Loading
- Return minimal data first, allow clients to request details
- Separate metadata from content calls
- Lazy loading of expensive computations (statistics, reviews)

### Content Management
- Implement content size limits per field
- Truncate with clear indicators ("... [truncated, X more characters]")
- Provide content preview functionality
- Compress repetitive content

## Questions for Team Discussion

1. **Backwards Compatibility**: How do we handle existing clients when we change response structures?

2. **Default Behavior**: Should tools default to minimal responses and require explicit requests for detailed data?

3. **Error Handling**: How should tools behave when a response would exceed limits? Truncate? Return error? Auto-paginate?

4. **Client Guidance**: What documentation/examples should we provide to help MCP clients use tools efficiently?

5. **Monitoring**: Should we track token usage patterns to proactively identify tools that might hit limits?

6. **Performance vs. Usability**: How do we balance response size limits with developer experience?

## Next Steps

- [ ] Analyze each MCP tool's typical response sizes and token usage patterns
- [ ] Define token budgeting guidelines for tool responses (target: <15,000 tokens to leave buffer)
- [ ] Prototype pagination/filtering solutions for high-volume tools (`list_agents`, `list_available_models`)
- [ ] Implement response size monitoring and alerting
- [ ] Create usage guidelines and best practices for MCP clients
- [ ] Design progressive enhancement patterns for large data responses
- [ ] Consider implementing streaming responses for tools that could benefit

## Implementation Priority

**High Priority** (actively failing):
- `list_agents` - Implement pagination and summary mode
- `list_available_models` - Implement model filtering and summary mode

**Medium Priority** (likely to fail with growth):
- `fetch_run_details` - Implement content truncation and field selection
- `get_agent_versions` - Implement pagination and schema summary mode

**Low Priority** (monitoring needed):
- `ask_ai_engineer` - Monitor response lengths, implement length limits if needed
- `search_runs_by_metadata` - Ensure pagination is enforced when uncommented

---

*Created: June 2025*
*Status: Initial discussion - awaiting team input*