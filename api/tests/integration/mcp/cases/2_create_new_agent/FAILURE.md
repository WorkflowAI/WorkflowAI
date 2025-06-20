**Failed assertions:**

- The OpenAI SDK is configured with an incorrect WorkflowAI base URL. The code uses `https://api.workflowai.io/v1` (line 14) but should use `https://run.workflowai.com/v1`
- Input variables are not used to pass the summary to the agent. The current implementation constructs a prompt directly rather than using input variables for the agent
