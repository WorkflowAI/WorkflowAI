# Errors

Agents can raise errors, for example when the underlying model fails to generate a response or when
there are content moderation issues.

All errors are wrapped in a `WorkflowAIError` that contains details about what happened.
The most interesting fields are:

- `code` is a string that identifies the type of error, see the [errors.py](https://github.com/WorkflowAI/python-sdk/blob/main/workflowai/core/domain/errors.py) file for more details
- `message` is a human readable message that describes the error

The `WorkflowAIError` is raised when the agent is called, so you can handle it like any other exception.

```python
from datetime import date
import workflowai
from pydantic import BaseModel, Field
from workflowai import Model, WorkflowAIError

# define your input and output fields
class Input(BaseModel):
    transcript: str
    call_date: date

class Output(BaseModel):
    positive_points: list[str] = Field(description="List of positive points from the call", default_factory=list)
    negative_points: list[str] = Field(description="List of negative points from the call", default_factory=list)

# define your agent
@workflowai.agent(model=Model.GEMINI_2_0_FLASH_LATEST)
async def analyze_call_feedback(input: Input) -> Output:
    """
    Analyze customer call feedback and extract positive and negative points.
    """
    ...

try:
    await analyze_call_feedback(
        CallFeedbackInput(
            transcript="[00:01:15] Customer: The product is great!",
            call_date=date(2024, 1, 15)
        )
    )
except WorkflowAIError as e:
    print(e.code)
    print(e.message)
```

#### Recoverable errors

Sometimes, the LLM outputs an object that is partially valid, good examples are:

- the model context window was exceeded during the generation
- the model decided that a tool call result was a failure

In this case, an agent that returns an output only will always raise an `InvalidGenerationError` which
subclasses `WorkflowAIError`.

However, an agent that returns a full run object will try to recover from the error by using the partial output.

```python

run = await agent(input=Input(name="John"))

# The run will have an error
assert run.error is not None

# The run will have a partial output
assert run.output is not None
```