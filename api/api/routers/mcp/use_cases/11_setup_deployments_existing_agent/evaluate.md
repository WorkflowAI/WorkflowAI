deployment must be successfully set up
the code must run
the model_name must use the deployment syntax: "meeting-summarizer/#1/production"
the agent_id must not be passed in the metadata
'messages' must be empty

Ex:

```python
response = client.beta.chat.completions.parse(
    model="meeting-summarizer/#1/production",
    messages=[],
    response_format=MeetingSummarizerOutput,  # Defines the output format for the agent (uses structured generation)
    extra_body={  # Extra body contains the variables, the "dynamic" parts of the agents instructions, with same placeholder {{}} where variables will be injected at runtime
        "input": {
            "current_datetime": "2025-06-10 10:00:00",
            "meeting_transcript": "...",
        },
    },
)
```
