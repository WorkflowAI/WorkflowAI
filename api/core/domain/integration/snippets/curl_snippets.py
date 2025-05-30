CURL_LANDING_PAGE_SNIPPET = """```bash
curl -X POST https://run.workflowai.com/v1/chat/completions \\
  -H "Authorization: Bearer $WORKFLOWAI_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "my-agent/gpt-4o",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is the capital of France?"}
    ]
  }'
```"""

CURL_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET = """```bash
curl -X POST https://run.workflowai.com/v1/chat/completions \\
  -H "Authorization: Bearer $WORKFLOWAI_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "sentiment-analyzer/gemini-2.0-flash-001",
    "messages": [
      {"role": "system", "content": "You are a sentiment analysis expert."},
      {"role": "user", "content": "Analyze the sentiment of the user\\'s text and provide your analysis in the specified JSON format: {{texts}}"}
    ],
    "input": {"text": "The movie was absolutely fantastic, a true masterpiece!"},
    "response_format": {
      "type": "json_schema",
      "json_schema": {
        "name": "SentimentAnalysis",
        "schema": {
          "type": "object",
          "properties": {
            "sentiment": {
              "type": "string",
              "enum": ["positive", "negative", "neutral"],
              "description": "The overall sentiment of the text."
            },
            "confidence": {
              "type": "number",
              "description": "Confidence score for the sentiment, between 0 and 1."
            },
            "explanation": {
              "type": "string",
              "description": "A brief explanation of why this sentiment was chosen."
            }
          },
          "required": ["sentiment", "confidence", "explanation"]
        }
      }
    }
  }'
```"""

CURL_INTEGRATION_CHAT_INITIAL_SNIPPET = """```bash
curl -X POST https://run.workflowai.com/v1/chat/completions \\
  -H "Authorization: Bearer <WORKFLOWAI_API_KEY_PLACEHOLDER> \\
  -H "Content-Type: application/json" \\
  -d '{
   ...
  }'
```"""


CURL_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET = """```bash
curl -X POST https://run.workflowai.com/v1/chat/completions \\
  ...
  -d '{
    "model": "<PROPOSED_AGENT_NAME_PLACEHOLDER>",
    ...
  }'
```"""
