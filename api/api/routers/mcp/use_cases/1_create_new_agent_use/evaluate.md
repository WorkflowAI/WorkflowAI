the code must run
the code must include the run.workflowai.com
the code must include the user's API key (or read it from the env)
the code must use input variables in messages {{variable_name}}
the code must use structured output (response_format=...)
the code must use client.beta.chat.completions.parse(...)
the agent id must be passed in the metadata ex: {"metadata": {"agent_id": "text_summarizer"}}
3 models must be suggested
the code must show how to run the agent on 3 different models