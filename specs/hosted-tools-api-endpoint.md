# Hosted Tools API Endpoint

## Overview

Implementation of a public API endpoint to expose WorkflowAI's hosted tools with comprehensive descriptions and input schemas. This serves as the single source of truth for hosted tools documentation.

> **Note**: The TODOs in this document are AI-generated suggestions. Guillaume has full discretion to determine what actually needs to be implemented based on project priorities and requirements.

## Implemented Features

### ✅ Public API Endpoint

- **Endpoint**: `GET /v1/tools/hosted`
- **Authentication**: None required (public endpoint)
- **Response**: Simple JSON array of hosted tools (name + description only)
- **Location**: `api/api/routers/tools_v1.py`

### ✅ Service Layer

- **Service**: `HostedToolsService`
- **Location**: `api/api/services/hosted_tools_service.py`
- **Source of Truth**: Uses `WorkflowAIRunner.internal_tools` mapping

### ✅ Response Schema

- **Schema**: `HostedToolResponse` and `HostedToolsListResponse`
- **Location**: `api/api/schemas/hosted_tools_schema.py`
- **Format**: Simple array with tool name and description (input schemas removed as hosted tools are used internally)

### ✅ Enhanced Tool Descriptions

- Updated all hosted tool function docstrings with comprehensive descriptions
- **Google Search**: Enhanced with API provider details (Serper.dev)
- **Perplexity Tools**: Added missing docstrings for all variants (sonar, sonar-reasoning, sonar-pro)
- **Browser Text**: Added clear limitations (text-only, no images, no interactions)

### ✅ MCP Integration

- Added `list_hosted_tools()` MCP tool for AI assistant discovery
- **Location**: `api/api/routers/mcp/mcp_server.py`

### ✅ Routing Configuration

- Added to public routes in `api/api/main.py` (no authentication required)
- Follows same pattern as `/v1/models` endpoint

## TODO: Testing & Validation

### 🔲 Tests

- [ ] **Test `HostedToolsService.list_hosted_tools()`**

  - Verify all tools from `ToolKind` enum are returned
  - Validate tool descriptions are not null/empty
  - Ensure tools are sorted by name
  - Test input schema extraction

- [ ] **Test `GET /v1/tools/hosted` endpoint**

  - Verify 200 status code for successful requests
  - Validate response structure matches `HostedToolsListResponse`
  - Ensure no authentication required
  - Test response content-type is `application/json`

- [ ] **Test MCP `list_hosted_tools()` tool**
  - Verify MCP tool returns success=True
  - Validate data structure includes tools

## TODO: Documentation & Deployment

### 🔲 Update Documentation Sites

- [ ] **Update docs to fetch from API**

  - Modify `docsv2/` documentation to fetch hosted tools from `/v1/tools/hosted`
  - Remove hardcoded tool lists in favor of dynamic API calls
  - Ensure docs show current tool descriptions and schemas

- [ ] **Update `docsv2/content/docs/agents/tools.mdx`**
  - Currently has hardcoded tool descriptions and examples
  - **Discussion Point for Guillaume**: Should we build a React component that fetches tools from `/v1/tools/hosted` API to maintain single source of truth, or manually update the documentation?
  - **Pros of API-driven docs**: Always up-to-date, single source of truth, automatic updates when tools change
  - **Cons of API-driven docs**: Requires client-side fetching, potential loading states, dependency on API availability
  - **Alternative**: Manual updates but risk of documentation drift

### 🔲 OpenAPI Documentation

- [ ] **Verify OpenAPI spec generation**
  - Ensure `/v1/tools/hosted` appears in generated OpenAPI docs
  - Validate response schema documentation
  - Test example responses in API documentation

## TODO: Performance & Monitoring

### 🔲 Performance Optimization

- [ ] **Caching considerations**
  - Evaluate if tool list should be cached (likely unnecessary due to static nature)
  - Consider response compression for larger tool lists

### 🔲 Monitoring

- [ ] **Add metrics/logging**
  - Track usage of `/v1/tools/hosted` endpoint
  - Monitor for errors in tool description extraction

## Current Hosted Tools

**⚠️ VERIFICATION NEEDED**: The API exposes 5 tools, but external documentation may only reference 3 tools:

**Definitely Documented Externally (3 tools):**

- `@search-google` - Google web search via Serper.dev
- `@perplexity-sonar-pro` - Enhanced Perplexity search
- `@browser-text` - Text-only web content extraction

**Possibly Internal/Undocumented (2 tools):**

- `@perplexity-sonar` - Basic Perplexity search
- `@perplexity-sonar-reasoning` - Perplexity with reasoning

> **Discussion Point**: Should all 5 tools be publicly exposed via the API, or should we filter to only the 3 tools that are officially documented externally? Guillaume should verify which tools are actually intended for public use.

## Architecture Benefits

- **Single Source of Truth**: Tool info comes directly from function implementations
- **Auto-sync**: Adding new tools automatically updates API and docs
- **Type Safety**: Pydantic models ensure consistent responses
- **Public Access**: No authentication barriers for discovery
- **MCP Compatible**: AI assistants can discover tools programmatically
