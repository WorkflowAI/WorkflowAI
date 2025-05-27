
## Basic example
```bash
curl -X POST https://run.workflowai.com/v1/chat/completions \
  -H "Authorization: Bearer $WORKFLOWAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ]
  }'
```


## Identifying your Agent
```bash
curl -X POST https://run.workflowai.com/v1/chat/completions \
  -H "Authorization: Bearer $WORKFLOWAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "my-agent/gpt-4o",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is the capital of France?"}
    ]
  }'
```

## Trying other models
```bash
curl -X POST https://run.workflowai.com/v1/chat/completions \
  -H "Authorization: Bearer $WORKFLOWAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "my-agent/gemini-2.0-flash-001",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is the capital of France?"}
    ]
  }'
```

# Sentiment Analysis example
```bash
curl -X POST https://run.workflowai.com/v1/chat/completions \
  -H "Authorization: Bearer $WORKFLOWAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sentiment-analyzer/gemini-2.0-flash-001",
    "messages": [
      {"role": "system", "content": "You are a sentiment analysis expert. You must output a sentiment, confidence and explaination in JSON"},
      {"role": "user", "content": "Analyze the sentiment of the user's text and provide your analysis in the specified JSON format: The movie was absolutely fantastic, a true masterpiece!"}
    ],
  }'
```


# Swithing to input variables
```bash
curl -X POST https://run.workflowai.com/v1/chat/completions \
  -H "Authorization: Bearer $WORKFLOWAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sentiment-analyzer/gemini-2.0-flash-001",
    "messages": [
      {"role": "system", "content": "You are a sentiment analysis expert. You must output a sentiment, confidence and explaination in JSON"},
      {"role": "user", "content": "Analyze the sentiment of the user's text and provide your analysis in the specified JSON format: {{texts}}"}
    ],
    "input": {"text": "The movie was absolutely fantastic, a true masterpiece!"}
  }'
```


# Using structred outputs
```bash
curl -X POST https://run.workflowai.com/v1/chat/completions \
  -H "Authorization: Bearer $WORKFLOWAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sentiment-analyzer/gemini-2.0-flash-001",
    "messages": [
      {"role": "system", "content": "You are a sentiment analysis expert."},
      {"role": "user", "content": "Analyze the sentiment of the user's text and provide your analysis in the specified JSON format: {{texts}}"}
    ],
    "input": {"text": "The movie was absolutely fantastic, a true masterpiece!"}
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
  }'
```



# Using deployments
```bash
curl -X POST https://run.workflowai.com/v1/chat/completions \
  -H "Authorization: Bearer $WORKFLOWAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sentiment-analyzer/#3/production",
    "messages": [],
    "input": {"text": "The movie was absolutely fantastic, a true masterpiece!"}
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
  }'
```
