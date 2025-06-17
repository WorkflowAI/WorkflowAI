# MCP Tool Response Token Limit Issues

## Problem Statement

We're experiencing issues with MCP (Model Context Protocol) tools returning responses that exceed the maximum allowed token limit of 25,000 tokens when used through Claude code as the MCP client.

## Current Errors

### Observed Issues
- `workflowai:list_agents(from_date: "2024-12-10T00:00:00Z")`: **249,108 tokens** (10x over limit)
- `list_available_models`: **32,007 tokens** (1.3x over limit)

## Discussion Points by MCP Tool

### `workflowai:list_agents`
- **Current Issue**: Returns 249,108 tokens - extremely large response
- **Discussion Points**:
  - Should we implement pagination by default?
  - What filtering options could reduce response size?
  - Should we limit the number of agents returned per call?
  - What fields in agent data are essential vs. optional?
  - Could we implement a "summary" vs "detailed" response mode?

### `list_available_models`
- **Current Issue**: Returns 32,007 tokens - moderately over limit
- **Discussion Points**:
  - Are we returning too much metadata per model?
  - Should we group models by category/provider?
  - Could we implement model filtering by capability/type?
  - What model information is essential for client decision-making?
  - Should we have separate endpoints for model listing vs. model details?

## General Solution Approaches to Discuss

### Pagination Strategies
- Cursor-based pagination
- Offset/limit pagination
- Page size recommendations

### Response Filtering
- Field selection (sparse fieldsets)
- Conditional inclusion of expensive fields
- Client-specified response formats

### Data Structure Optimization
- Removing redundant information
- Compressing common patterns
- Using references instead of full objects

### Alternative Approaches
- Streaming responses
- Multi-call patterns with smaller chunks
- Caching strategies for frequently requested data

## Questions for Team Discussion

1. **Backwards Compatibility**: How do we handle existing clients when we change response structures?

2. **Default Behavior**: Should tools default to minimal responses and require explicit requests for detailed data?

3. **Error Handling**: How should tools behave when a response would exceed limits? Truncate? Return error? Auto-paginate?

4. **Client Guidance**: What documentation/examples should we provide to help MCP clients use tools efficiently?

5. **Monitoring**: Should we track token usage patterns to proactively identify tools that might hit limits?

## Next Steps

- [ ] Analyze each MCP tool's typical response sizes
- [ ] Define token budgeting guidelines for tool responses
- [ ] Prototype pagination/filtering solutions for high-volume tools
- [ ] Create usage guidelines for MCP clients
- [ ] Implement token usage monitoring

---

*Created: December 2024*
*Status: Initial discussion - awaiting team input*