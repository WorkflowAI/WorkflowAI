# Parameters

[TODO: @guillaq]

`POST` `/v1/chat/completions`

Request body

TODO: use https://mintlify.com/docs/components/fields

- `messages` (required)
- `model` (required)
- `stream` (optional) [Learn more about streaming](/docs/guides/streaming.md)
- `temperature` (optional)
- `max_tokens` (optional)
- `top_p` (optional)
- `frequency_penalty` (optional)
- `presence_penalty` (optional)
- `stop` (optional)
- `extra_body` (optional)

### Parameters not supported from OpenAI

- ...

## `extra_body` (optional)

- `agent_id` (optional)
- ..