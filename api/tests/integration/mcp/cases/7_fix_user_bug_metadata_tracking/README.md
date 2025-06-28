## Scenario 7: Fix User Bug When Agent Lacks Metadata Tracking

### initial state:

```
- agent is deployed on WorkflowAI in production
- agent is NOT collecting user_id or other metadata for runs
```

### goal:

```
- user_id "usr_67890" reports a bug with agent "agent_xyz789"
- fix this bug for this specific user
- but first need to implement proper metadata collection
- then investigate and resolve the user's issue
```

### what is required:

- modify agent code to collect user_id metadata for all runs
- deploy updated agent with metadata tracking
- implement proper metadata logging
- investigate user's specific issue once tracking is in place
- provide bug resolution
