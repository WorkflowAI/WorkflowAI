## Scenario 6: Investigate User's Bad Agent Experience

### initial state:

```
- agent is deployed on WorkflowAI in production
- agent logs all runs with metadata including "user_id"
```

### goal:

```
- user_id "usr_12345" just got a bad experience with agent "agent_abc123"
- find out what happened in that specific interaction
- analyze the agent's behavior for that user
- identify potential issues or failure points
- understand if this is a recurring problem for this user or others
```

### what is required:

- ability to query runs by user_id and agent_id
- retrieve specific run details and execution traces
- analyze user interaction patterns
- identify failure points or issues
- provide recommendations to prevent similar issues
