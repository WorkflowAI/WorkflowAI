# Workflows

{% hint style="info" %}
This section is intended for developers who want to build complex workflows by orchestrating multiple AI agents. You'll learn how to break down complex tasks into simpler agents and combine them effectively.
{% endhint %}

{% hint style="info" %}
This documentation is inspired by Anthropic's research on [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents).
{% endhint %}

## Workflows

Workflows are a way to orchestrate multiple agents to achieve a complex task.
For example: imagine you want to extract the names of founders from this YC batch: https://www.ycombinator.com/companies?batch=W25 
Since the founders' names are available on another page, we need to create two agents:
- one agent to extract the list of companies, and their URLs 
- another agent will, for each company, extract the founders' names

## Best practices

### Break down a task into multiple agents
- each agent can be simpler, with less instructions, and less likely to hallucinate
- each agent can be optmized for its specific step, by picking the right model and tools, increasing the quality of each step, while reducing the cost.
- you can run multiple agents in parallel, and combine their results, reducing latency.

## Setup a workflow

We will be using code to orchestrate the agents. We recommend using CursorAI to write the code.

{% hint style="info" %}
Read about our CursorAI integration [here](integrations/cursor.md) first.
{% endhint %}

### Patterns

These building blocks can be combined with workflow patterns that help manage complexity:

| Pattern | Description |
|---------|-------------|
| Sequential Processing | Steps executed in order |
| Parallel Processing | Independent tasks run simultaneously |
| Evaluation/Feedback Loops | Results checked and improved iteratively |
| Orchestration | Coordinating multiple components |
| Routing | Directing work based on context |



Write the workflow you want to setup in CursorAI:
> Given a YC batch URL (e.g., https://www.ycombinator.com/companies?batch=W25), follow these steps:
>
> 1. First, visit the batch URL and extract all company profile URLs by:
>    - Looking for company cards/links on the page
>    - Collecting each company's profile URL
>    - Store these URLs for the next step
>
> 2. Then, for each company profile URL:
>    - Visit the company's page
>    - Find and extract the founder names
>    - Keep track of both the company name and its founders

CursorAI will generate the code for you. The code, when run for the first time, might create new agents on WorkflowAI.

> https://workflowai.dev/workflowai/tasks/workflow-builder/1?groupIteration=9&showDiffMode=false&show2ColumnLayout=false&taskRunId1=1923d00c-5034-423c-922f-df06e7f6d38c&taskRunId2=663aea18-dcd9-47be-a281-ac7dcedbff42&taskRunId3=bebea544-7b64-46bd-b186-6c61bd4d10c4&taskRunId=bebea544-7b64-46bd-b186-6c61bd4d10c4
```python
import workflowai
from pydantic import BaseModel
from typing import List, Optional

# Define schemas for each task
class ScrapeListInput(BaseModel):
    url: str = 'https://www.ycombinator.com/companies/w25'

class ScrapeListOutput(BaseModel):
    company_urls: List[str]
    company_names: List[str]

class ScrapeCompanyInput(BaseModel):
    company_url: str

class ScrapeCompanyOutput(BaseModel):
    founder_names: List[str]

class CompanyData(BaseModel):
    company_name: str
    founder_names: List[str]

class FinalOutput(BaseModel):
    companies: List[CompanyData]

# Define tasks
@workflowai.task(schema_id=1, model='gpt-4-turbo', version='production')
async def scrape_yc_list(task_input: ScrapeListInput) -> ScrapeListOutput:
    ...

@workflowai.task(schema_id=2, model='gpt-4-turbo', version='production')
async def scrape_company_page(task_input: ScrapeCompanyInput) -> ScrapeCompanyOutput:
    ...

async def main():
    # Initialize list scraping
    list_input = ScrapeListInput()
    list_result = await scrape_yc_list(list_input)
    
    # Process each company
    companies = []
    for i, company_url in enumerate(list_result.company_urls):
        company_input = ScrapeCompanyInput(company_url=company_url)
        company_result = await scrape_company_page(company_input)
        
        companies.append(CompanyData(
            company_name=list_result.company_names[i],
            founder_names=company_result.founder_names
        ))
    
    # Return final results
    return FinalOutput(companies=companies)

if __name__ == '__main__':
    import asyncio
    result = asyncio.run(main())
    
    # Print results
    for company in result.companies:
        print(f'Company: {company.company_name}')
        print(f'Founders: {
```

## Workflow: Parallelization
LLMs can sometimes work simultaneously on a task and have their outputs aggregated programmatically. This workflow, parallelization, manifests in two key variations:

Sectioning: Breaking a task into independent subtasks run in parallel.
Voting: Running the same task multiple times to get diverse outputs.

[how to build with WorkflowAI]

> https://github.com/anthropics/anthropic-cookbook/blob/main/patterns/agents/basic_workflows.ipynb

> https://www.agentrecipes.com 

### Example
Ask multiple agents for an answer, and aggregate the results.

> https://workflowai.dev/workflowai/tasks/workflow-builder/1/runs?taskRunId=fe2c5323-fbcd-4b9e-ab91-426e55aec410
```python
import workflowai
from typing import List
from pydantic import BaseModel

# Input/Output schemas for the agents
class QuestionInput(BaseModel):
    question: str

class AnswerOutput(BaseModel):
    answer: str

class AggregatedOutput(BaseModel):
    combined_answer: str
    individual_answers: List[str]

# Define the agents
@workflowai.task(schema_id=1, model="gpt-4-latest", version="production")
async def expert_agent_1(task_input: QuestionInput) -> AnswerOutput:
    ...

@workflowai.task(schema_id=2, model="gpt-4-latest", version="production")
async def expert_agent_2(task_input: QuestionInput) -> AnswerOutput:
    ...

@workflowai.task(schema_id=3, model="gpt-4-latest", version="production")
async def expert_agent_3(task_input: QuestionInput) -> AnswerOutput:
    ...

@workflowai.task(schema_id=4, model="gpt-4-latest", version="production")
async def answer_aggregator(answers: List[str]) -> AggregatedOutput:
    ...

async def run_multi_agent_workflow(question: str):
    # Create input
    question_input = QuestionInput(question=question)
    
    # Get answers from all experts in parallel
    tasks = [
        expert_agent_1(question_input),
        expert_agent_2(question_input),
        expert_agent_3(question_input)
    ]
    
    responses = await asyncio.gather(*tasks)
    
    # Extract answers
    answers = [response.task_output.answer for response in responses]
    
    # Aggregate answers
    final_result = await answer_aggregator(answers)
    
    return final_result.task_output

# Example usage
async def main():
    result = await run_multi_agent_workflow("What are the main challenges in artificial intelligence?")
    print("Combined Answer:", result.combined_answer)
    print("Individual Answers:", result.individual_answers)
```

## Workflow: Routing

Routing classifies an input and directs it to a specialized followup task. This workflow allows for separation of concerns, and building more specialized prompts. Without this workflow, optimizing for one kind of input can hurt performance on other inputs.

> https://github.com/anthropics/anthropic-cookbook/blob/main/patterns/agents/basic_workflows.ipynb

### Example
Routing a customer support request to the right agent.

```python
import workflowai
from pydantic import BaseModel
from typing import Optional, Literal

# Input/Output schemas for the agents
class CustomerRequestInput(BaseModel):
    customer_message: str

class CustomerRequestOutput(BaseModel):
    department: Literal['customer_success', 'sales']
    reason: str

class CustomerSuccessInput(BaseModel):
    customer_message: str
    context: str

class CustomerSuccessOutput(BaseModel):
    response: str
    follow_up_needed: bool

class SalesInput(BaseModel):
    customer_message: str
    context: str

class SalesOutput(BaseModel):
    response: str
    opportunity_score: int

# Define the workflow tasks
@workflowai.task(schema_id=1, model="gpt-4-latest", version="production")
async def route_customer_request(task_input: CustomerRequestInput) -> CustomerRequestOutput:
    ...

@workflowai.task(schema_id=2, model="gpt-4-latest", version="production")
async def handle_customer_success(task_input: CustomerSuccessInput) -> CustomerSuccessOutput:
    ...

@workflowai.task(schema_id=3, model="gpt-4-latest", version="production")
async def handle_sales(task_input: SalesInput) -> SalesOutput:
    ...

# Main workflow function
async def handle_customer_request(customer_message: str):
    # First, route the request
    routing_input = CustomerRequestInput(customer_message=customer_message)
    routing_result = await route_customer_request(routing_input)
    
    # Based on routing, handle with appropriate agent
    if routing_result.department == 'customer_success':
        cs_input = CustomerSuccessInput(
            customer_message=customer_message,
            context=f"Routing reason: {routing_result.reason}"
        )
        response = await handle_customer_success(cs_input)
    else:  # sales
        sales_input = SalesInput(
            customer_message=customer_message,
            context=f"Routing reason: {routing_result.reason}"
        )
        response = await handle_sales(sales_input)
    
    return response
```

## Workflow: Orchestrator-workers
In the orchestrator-workers workflow, a central LLM dynamically breaks down tasks, delegates them to worker LLMs, and synthesizes their results.

## Workflow: Evaluator-optimizer
In the evaluator-optimizer workflow, one LLM call generates a response while another provides evaluation and feedback in a loop.

### Example
Ask an agent to write a blog post, and another agent to evaluate the blog post and provide feedback.

> https://workflowai.dev/workflowai/tasks/workflow-builder/1/runs?taskRunId=d54774fb-0ea5-44d1-8521-1d0fa3676905
```python
import workflowai
from pydantic import BaseModel
from typing import Optional

# Input/Output schemas for blog writer
class BlogWriterInput(BaseModel):
    topic: Optional[str] = None
    target_length: Optional[int] = None

class BlogWriterOutput(BaseModel):
    blog_post: str

# Input/Output schemas for blog evaluator
class BlogEvaluatorInput(BaseModel):
    blog_post: str

class BlogEvaluatorOutput(BaseModel):
    feedback: str
    rating: int
    improvement_suggestions: list[str]

@workflowai.task(schema_id=1, model="gpt-4-latest", version="production")
async def blog_writer_task(task_input: BlogWriterInput) -> BlogWriterOutput:
    ...

@workflowai.task(schema_id=2, model="gpt-4-latest", version="production")
async def blog_evaluator_task(task_input: BlogEvaluatorInput) -> BlogEvaluatorOutput:
    ...

async def run_blog_workflow(topic: str, target_length: int = 800):
    try:
        # Step 1: Write the blog post
        writer_input = BlogWriterInput(topic=topic, target_length=target_length)
        writer_result = await blog_writer_task(writer_input)
        
        # Step 2: Evaluate the blog post
        evaluator_input = BlogEvaluatorInput(blog_post=writer_result.task_output.blog_post)
        evaluator_result = await blog_evaluator_task(evaluator_input)
        
        # Print results
        print("Blog Post:\n", writer_result.task_output.blog_post)
        print("\nEvaluation:")
        print(f"Rating: {evaluator_result.task_output.rating}/10")
        print("Feedback:", evaluator_result.task_output.feedback)
        print("Improvement Suggestions:")
        for suggestion in evaluator_result.task_output.improvement_suggestions:
            print(f"- {suggestion}")
            
    except workflowai.WorkflowAIError as e:
        print(f"Error: Code={e.error.code}, Message={e.error.message}")

```