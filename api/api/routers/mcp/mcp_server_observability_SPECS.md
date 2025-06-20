# Goal

Since we are releasing our MCP server to our users, we want to keep an eye on all the calls to our MCP server to make sure the service is working as expected, and to find use cases to improve upon.

# Proposal

## Data collection
We'll write a simple Starlette middleware that will capture:
- The MCP tool name
- The MCP tool call arguments
- The MCP tool call response
- The user's id

Notes from Yann: I've tried to find the session id in the request but could not for now.


## Data analysis with `MCP Tool Call Analyzer Agent`
Once this data is captured, we'll run an agent to "vibe check" that the MCP tool call went well. This agent's runs will be our "audit trail" of the MCP server.

Agent input variables:
- The MCP tool name
- The MCP tool call arguments
- The MCP tool call response

Agent metadata:
- Who is the user

Agent output:
- Is call successful?
- If not:
    - Is it a client error? (wrong arguments passed)
    - Is it a server error? (tool failed)
    - Propose an enhancement suggestion (those enhancement suggestions can be used to improve the MCP server)

## Evaluating "conversations" as a whole
It could be useful to evaluate a whole Cursor chat at once instead of every turn of back and forth between Cursor and the MCP server.

Possible implementation:
- Do nothing, and consider turn by turn evaluation is good enough. If what we mostly care about is behaviour of the MCP server at every step of the conversation, I (Yann) think that this paradigm works reasonably well.
But we won't evaluate the ability of the client to reason about the whole conversation. You might ask "why evaluate clients at all" ? Because we want to make sure our tools and description are clear enough for the client, and improve their understanding of the MCP server.

- Consider all MCP tool calls of a given `user_id` of the last X minutes, and evaluate the whole conversation at once.

- User MCP session id or similar ? (I could not find a way to get the session id in the request for now...)

- Use `reply_to_message_id` or similar to identify the conversation.

## Monitoring process
We can just check our runs at regular intervals to see if there are any issues. We can simply filter on the 'is_success' field in output to see failures, or filter on user_id to see if there are any issues with a given user.

Next step:
[ ] Finish implementation in https://github.com/WorkflowAI/WorkflowAI/pull/518
[ ] Investigate if we can get the session id in the request to work on a whole conversation instead of turn by turn (check modelcontextprotocol/python-sdk)