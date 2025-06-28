# Discussion: Anthropic's Multi-Agent Research System

**Date**: June 15, 2025
**Article**: [How we built our multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system)
**Review**: [Simon Willison's analysis](https://simonwillison.net/2025/Jun/14/multi-agent-research-system/)

- [ ] Pierre: the part about evaluations is very interesting. Guillaume is working this week already on setting up the evaluation framework by using Claude Code and giving actual tasks to Claude Code to complete using our MCP server.

Quote:
> **End-state evaluation of agents that mutate state over many turns.** Evaluating agents that modify persistent state across multi-turn conversations presents unique challenges. Unlike read-only research tasks, each action can change the environment for subsequent steps, creating dependencies that traditional evaluation methods struggle to handle. We found success focusing on end-state evaluation rather than turn-by-turn analysis. Instead of judging whether the agent followed a specific process, evaluate whether it achieved the correct final state. This approach acknowledges that agents may find alternative paths to the same goal while still ensuring they deliver the intended outcome. For complex workflows, break evaluation into discrete checkpoints where specific state changes should have occurred, rather than attempting to validate every intermediate step.

I bet that, given some non-passing tests, Codex or Cursor might be able to actually fix the code, including tool descriptions from the MCP server.

- [ ] Pierre: Do we need to run evals on the `ask_ai_engineer` tool in the MCP server? Or can we skip the evals of `ask_ai_engineer` and only test end-to-end? @yannbu

- [ ] Memory management to sustain long conversations.

Quote:
> Long-horizon conversation management. Production agents often engage in conversations spanning hundreds of turns, requiring careful context management strategies. As conversations extend, standard context windows become insufficient, necessitating intelligent compression and memory mechanisms. We implemented patterns where agents summarize completed work phases and store essential information in external memory before proceeding to new tasks. When context limits approach, agents can spawn fresh subagents with clean contexts while maintaining continuity through careful handoffs. Further, they can retrieve stored context like the research plan from their memory rather than losing previous work when reaching the context limit. This distributed approach prevents context overflow while preserving conversation coherence across extended interactions.

- [ ] Avoid the "game of telephone" by using a `curl` to fetch data from our API.

Quote:
> Subagent output to a filesystem to minimize the ‘game of telephone.’ Direct subagent outputs can bypass the main coordinator for certain types of results, improving both fidelity and performance. Rather than requiring subagents to communicate everything through the lead agent, implement artifact systems where specialized agents can create outputs that persist independently. Subagents call tools to store their work in external systems, then pass lightweight references back to the coordinator. This prevents information loss during multi-stage processing and reduces token overhead from copying large outputs through conversation history. The pattern works particularly well for structured outputs like code, reports, or data visualizations where the subagent's specialized prompt produces better results than filtering through a general coordinator.

Imagine the use-case where the MCP client needs to fetch all the runs that are associated with a given agent. Instead of using the `list_runs` tool, which will result in a lot of tokens copied between the MCP tool call response and the MCP client, a `curl` command could be used to fetch the data from our API.