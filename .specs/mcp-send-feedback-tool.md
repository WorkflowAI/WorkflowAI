# MCP Send Feedback Tool

## Overview

The `send_feedback` tool enables MCP clients (AI agents) to automatically submit feedback about their experience using the MCP server. This feedback is processed asynchronously by a dedicated AI agent for analysis and categorization.

## How It Works

### 1. Feedback Submission
MCP clients call the `send_feedback` tool with:
- **feedback**: Their experience using the MCP server (required)
- **context**: Optional details about which operations generated the feedback

The tool immediately returns an acknowledgment that the feedback was received.

### 2. Asynchronous Processing
The feedback is sent to a dedicated WorkflowAI agent (`mcp-feedback-processing-agent`) that:
- Analyzes the feedback content
- Classifies sentiment (positive, negative, neutral)
- Identifies key themes
- Provides a confidence score

Processing happens in the background without blocking the MCP client.

### 3. Metadata Tracking
Each feedback submission includes:
- Organization name (from authentication context)
- User email (if available)
- Agent ID for tracking and analytics

This enables searching and analyzing feedback patterns across organizations using the existing `search_runs_by_metadata` tool.

## Purpose

- **Automated Quality Monitoring**: Collect systematic feedback from AI agents about MCP server performance
- **Issue Detection**: Identify common problems or pain points in MCP operations
- **Usage Analytics**: Track satisfaction and usage patterns by organization
- **Continuous Improvement**: Guide enhancements to MCP server functionality based on real usage data

## Example Usage

```python
# MCP client submits feedback after operations
await send_feedback(
    feedback="All MCP tools responded quickly and returned expected results",
    context="Used list_agents and search_runs tools in sequence"
)
```

The feedback is acknowledged immediately while analysis happens asynchronously in the background.
