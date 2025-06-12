---
title: Thinking Mode
description: Enable thinking mode on capable models and retrieve the thoughts.
---

import { Tabs, Tab } from 'fumadocs-ui/components/tabs';
import { Callout } from 'fumadocs-ui/components/callout';

## What is Thinking Mode?

Thinking mode is an advanced reasoning capability available in certain AI models that allows them to engage in explicit step-by-step reasoning before providing their final answer. When thinking mode is enabled, the model generates internal "thoughts" that show its reasoning process, problem-solving steps, and decision-making logic.

Thinking mode can unlock better inference capabilities in complex use cases; however, it can add extra cost and latency, since the **thoughts** are generated prior to the response and count towards the used tokens. It is important to consider the trade-off when enabling thinking mode.

## Configuration

All providers have a different way of configuring thinking mode or returning thoughts:
- [OpenAI](https://platform.openai.com/docs/guides/reasoning) and [xAI](https://docs.x.ai/docs/guides/reasoning) expose a **reasoning effort** parameter (`low`, `medium`, `high`).
- [Anthropic](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking) and [Google](https://ai.google.dev/gemini-api/docs/thinking) allow providing a thinking budget, limiting the number of tokens used for thinking.
- Fireworks does not support configuring thinking mode

To rationalize differences between providers, WorkflowAI relies on the completion API [reasoning effort parameter](https://platform.openai.com/docs/api-reference/chat/create#chat-create-reasoning_effort) and allows passing either:
- an OpenAI style reasoning effort (`low`, `medium`, `high`), which is converted to a thinking budget when needed.
- `highest` which will be converted to the max number of tokens for thinking depending on the model
- an `integer` for a thinking budget, which is converted to a reasoning effort when needed

The mapping from reasoning effort to thinking budget is described in the below table. The reverse mapping follows a similar pattern.

| Reasoning Effort | Thinking Budget |
|-----------------|-----------------|
| `low`           | 1024            |
| `medium`        | 8192            |
| `high`          | 16384           |
| `highest`       | max output tokens of the model - 1           |

## Usage

As explained above, the reasoning effort can be passed as a parameter to the completion API. Thoughts can then be retrieved from the choice object via a WorkflowAI specific field `reasoning_content`.

<Callout type="warning">
As the `reasoning_content` field is not part of the OpenAI API, it will likely throw a typing issue when accessed.
</Callout>

<Tabs items={["Python", "TypeScript", "JSON"]}>
  <Tab>
  ```python
  res = openai.chat.completions.create(
    model="o3-mini",
    messages=[{"role": "user", "content": "What is the meaning of life?"}],
    reasoning_effort="high", # or e.g. 16384
  )
  # Access the thoughts
  print(res.choices[0].message.reasoning_content) # type: ignore
  ```
  </Tab>
  <Tab>
  ```typescript
  const res = await openai.chat.completions.create({
    model: "o3-mini",
    messages: [{ role: "user", content: "What is the meaning of life?" }],
    reasoning_effort: "high", // or e.g. 16384
  });
  // Access the thoughts
  // @ts-expect-error - reasoning_content is not part of the OpenAI API
  console.log(res.choices[0].message.reasoning_content); 
  ```
  </Tab>
  <Tab>
  ```json
  {
    "model": "o3-mini",
    "messages": [
      {
        "role": "user", 
        "content": "What is the meaning of life?"
      }
    ],
    "reasoning_effort": "high"
  }
  ```
  </Tab>
</Tabs>

<Callout type="info">
When streaming, the thoughts deltas are also returned beside the content.
</Callout>

<Callout type="info">
For historic reasons, the reasoning effort can sometimes be included in the model id, e.g. `o3-2025-04-16-high`. Passing the reasoning effort separately from the model id is now preferred.
</Callout>
