# Meta Agent Documentation Conversion Summary

## Overview
Successfully converted the Meta Agent documentation from always-loaded to an on-demand search tool, improving performance by removing automatic documentation fetching on every request.

## Changes Made

### 1. Added Search Documentation Tool (`/workspace/api/core/agents/meta_agent_proxy.py`)

#### New Tool Definition
- Added `SEARCH_DOCUMENTATION_TOOL: ChatCompletionToolParam` with:
  - Tool name: `search_documentation`
  - Description: Search WorkflowAI documentation for relevant information
  - Parameters: `query` (string) - specific search query

#### Updated Tool Parsing
- Added `search_documentation_query: str | None = None` to `ParsedToolCall`
- Updated `parse_tool_call()` function to handle `search_documentation` tool calls
- Added `search_documentation_request: str | None` to `ProxyMetaAgentOutput`

#### Updated Tool Lists
- Added `SEARCH_DOCUMENTATION_TOOL` to `TOOL_DEFINITIONS`
- Updated `proxy_meta_agent()` to include search documentation request in output

#### Updated Instructions
- Added `<documentation_search>` section to `GENERIC_INSTRUCTIONS`
- Provided guidance on when and how to use the search documentation tool

### 2. Updated Meta Agent Service (`/workspace/api/api/services/internal_tasks/meta_agent_service.py`)

#### New Tool Call Type
- Added `SearchDocumentationToolCall(MetaAgentToolCall)` class
- Updated `MetaAgentToolCallType` to include the new tool call
- Added proper field validation and domain conversion methods

#### Removed Automatic Documentation Loading
- Removed automatic `get_relevant_doc_sections()` calls from `_build_meta_agent_input()`
- Removed automatic documentation loading from `_build_proxy_meta_agent_input()`
- Removed `_pick_relevant_doc_sections()` method (no longer needed)
- Set `workflowai_documentation_sections=[]` by default

#### Updated Tool Call Handling
- Updated `_extract_tool_call_to_return()` to handle search documentation requests
- Added `search_documentation_request: str | None` parameter
- Added logic to create `SearchDocumentationToolCall` when search is requested

#### Updated Response Streaming
- Added `search_documentation_request_chunk` variable to capture search requests
- Updated chunk processing to handle search documentation requests
- Updated `_extract_tool_call_to_return()` call to pass search documentation parameter

#### Added Documentation Search Handler
- Added `_handle_search_documentation_tool_call()` method
- Integrates with existing `DocumentationService.search_documentation_by_query()`
- Returns formatted search results with proper error handling
- Limits results to top 3 sections for performance

## Performance Impact

### Before
- **"Hello" query**: 10.41s (with automatic documentation loading)
- **"How can I deploy my agent?"**: 22.95s (with automatic documentation loading)

### Expected After
- **"Hello" query**: Significant improvement (no documentation loading)
- **"How can I deploy my agent?"**: Faster initial response + on-demand search when needed

## Key Benefits

1. **Performance**: Eliminates automatic documentation loading on every request
2. **Relevance**: Documentation is only searched when specifically needed
3. **Flexibility**: Agent can search for specific topics based on user questions
4. **Scalability**: Reduces load on documentation service for simple queries

## Integration Points

The search documentation tool integrates with:
- Existing `DocumentationService.search_documentation_by_query()` method
- Existing `search_documentation_agent()` for intelligent document retrieval
- Standard meta agent tool call framework
- Frontend tool call execution system

## Usage Flow

1. User asks a question requiring documentation
2. Meta agent determines documentation search is needed
3. Meta agent calls `search_documentation` tool with specific query
4. Frontend/API executes the tool call
5. `DocumentationService.search_documentation_by_query()` performs the search
6. Results are returned and formatted for the user
7. Meta agent provides answer based on retrieved documentation

## Files Modified

1. `/workspace/api/core/agents/meta_agent_proxy.py` - Added search tool and parsing
2. `/workspace/api/api/services/internal_tasks/meta_agent_service.py` - Updated service logic

## Testing Recommendations

1. Test "Hello" query performance improvement
2. Test "How can I deploy my agent?" with on-demand search
3. Verify search tool is properly triggered for documentation questions
4. Test error handling when documentation search fails
5. Verify tool call execution in frontend

## Notes

- The existing `DocumentationService` and `search_documentation_agent` remain unchanged
- All existing documentation search functionality is preserved
- The change is backward compatible with existing tool call framework
- Error handling is included for failed documentation searches