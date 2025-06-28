# MCP Test Cases

## Structure

This directory contains the test cases for the MCP server.

Each test case is a directory with the following structure:

- `initial_state`: The initial state of the test case.
- `PROMPT.md`: The prompt for the test case.
- `README.md`: A README explaining the test case

### Notes

- `CLAUDE.md` is dynamically added to each initial state directory
  before running each test. This is the best way we found to make sure that Claude considers the `initial_state`
  directory as the root of the project. Without it, it seems that Claude tries to grep the root of the current repo.

## Running test cases manually

### Claude Code

> Claude code is included in the project as a dev dependency. So it can be installed with `yarn install`

```sh
# Make sure that the MCP server is added to claude
WORKFLOWAI_API_HOST=https://api.workflowai.com
WORKFLOWAI_API_KEY=wai-...
claude mcp add workflowai $WORKFLOWAI_API_HOST/mcp/ -H "Authorization: Bearer $WORKFLOWAI_API_KEY" --transport http

# CD into the test case initial state directory
cd ../<test_case_name>/initial_state

# Add the CLAUDE.md file to the initial state directory
cp ../../_CLAUDE.md CLAUDE.md

# cat the PROMPT.md file and pass it to claude -p
cat ../PROMPT.md | claude --verbose
```
