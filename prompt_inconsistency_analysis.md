# Prompt Inconsistency Analysis - Internal Agents

## Overview

This document analyzes prompt inconsistencies across all internal agents in the WorkflowAI codebase. The analysis covers 50+ agents found in `api/core/agents/` and identifies patterns, inconsistencies, and recommendations for standardization.

## Summary of Findings

| Category | Issues Found | Severity | Examples |
|----------|-------------|----------|----------|
| Prompt Definition Methods | 4 different patterns | High | Docstrings, INSTRUCTIONS constants, inline, templated |
| Terminology | 3+ naming inconsistencies | High | "prompt" vs "instructions" vs "messages" |
| Model Configuration | 3 different patterns | Medium | Direct model, VersionProperties, string-based |
| Prompt Structure | Highly variable | Medium | XML tags vs markdown headers vs plain text |
| Templating Usage | Inconsistent application | Medium | Heavy Jinja2 vs none at all |
| Function Naming | 5+ different patterns | Low | Various verb/noun combinations |
| Import Patterns | 3 different approaches | Low | workflowai vs Model vs OpenAI direct |
| Detail Levels | Extreme variance | Medium | 1 sentence vs 300+ lines |

## Major Inconsistencies Found

### 1. Inconsistent Prompt Definition Methods

**Pattern A: Function Docstrings**
```python
@workflowai.agent(id="improve-prompt")
async def run_improve_prompt_agent(_: ImprovePromptAgentInput) -> ImprovePromptAgentOutput:
    """Given an original agent config (prompt, input schema, output schema), an optiona example agent run (input, output) and a user evaluation, generate the following:

    - An improved prompt
    - A changelog
    - A list of field updates for the input schema
    """
```

**Pattern B: INSTRUCTIONS Constants**
```python
INSTRUCTIONS = """You are an expert at suggesting AI agent names.

You will be given a raw LLM content, and you need to suggest an agent name for it.

The agent name should be a short name that is easy to remember and that is relevant to the content.
"""

@workflowai.agent(
    version=workflowai.VersionProperties(
        instructions=INSTRUCTIONS,
        model=workflowai.Model.GEMINI_2_0_FLASH_001,
    ),
)
```

**Pattern C: Direct Embedding in Decorator**
```python
@workflowai.agent(
    version=workflowai.VersionProperties(
        instructions=META_AGENT_INSTRUCTIONS,
        model=workflowai.Model.CLAUDE_3_7_SONNET_20250219,
    ),
)
```

**Pattern D: Complex Templated Instructions (AI Engineer Agent)**
```python
AI_ENGINEER_INSTRUCTIONS = """
You are the WorkflowAI AI Engineer agent. Your role is to help users build, improve, and debug their WorkflowAI agents directly from their IDE (Cursor, Windsurf, etc.).

<current_datetime>
Current datetime is: {{current_datetime}}
</current_datetime>

<user_code>
The user is using the following programming language: {{user_programming_language}}
"""
```

### 2. Inconsistent Prompt Structure and Organization

**Highly Structured (Meta Agent)**
- Uses clear section headers with `#` and `##`
- Organized into logical sections: concepts, guidelines, tools
- Extensive use of examples and formatting

**Minimally Structured (Simple Agents)**
- Single paragraph descriptions
- No section headers
- Minimal formatting

**Custom Structure (AI Engineer Agent)**
- Uses XML-style tags: `<current_datetime>`, `<user_code>`
- Extensive conditional templating with Jinja2
- Complex nested sections

### 3. Inconsistent Variable Naming and Terminology

**Terminology Inconsistencies:**
- `"prompt"` vs `"instructions"` vs `"messages"`
- `"agent"` vs `"task"` (legacy naming)
- `"improve_prompt"` vs `"improve_instructions"`

**Examples:**
- `improve_prompt.py` uses "prompt" in function name but "instructions" in context
- `agent_name_suggestion_agent.py` vs task-based naming in other files
- `ImprovePromptToolCallRequest` vs `instruction_improvement_request_message`

### 4. Inconsistent Model Configuration Patterns

**Direct Model Reference:**
```python
@workflowai.agent(model=Model.GEMINI_2_0_FLASH_001)
```

**Version Properties:**
```python
@workflowai.agent(
    version=workflowai.VersionProperties(
        model=workflowai.Model.GEMINI_2_0_FLASH_001,
        temperature=0.5,
    ),
)
```

**String-based Model References:**
```python
model="gemini-2.5-flash"
```

### 5. Inconsistent Jinja2 Templating Usage

**Heavy Templating (AI Engineer Agent):**
```python
{% if current_agent_context %}
IMPORTANT: In case of discrepancies between the user code extract and the current_agent_context, use the user code extract as the source of truth.
{% endif %}
```

**Moderate Templating (Search Documentation Agent):**
```python
{% if usage_context %}
## Context
The usage context is:
{{usage_context}}
{% endif %}
```

**No Templating (Simple Agents):**
Most simple agents use no templating at all.

### 6. Inconsistent Prompt Style and Tone

**Conversational Style (Meta Agent):**
```
"You are WorkflowAI's meta-agent. You are responsible for helping WorkflowAI's users enhance their agents..."
```

**Technical/Formal Style (Improve Prompt Agent):**
```
"Given an original agent config (prompt, input schema, output schema), an optiona example agent run..."
```

**Command Style (Simple Agents):**
```
"Suggest the closest supported model name for a given invalid model input."
```

### 7. Inconsistent Detail Levels

**Extremely Detailed (Meta Agent):**
- 300+ lines of instructions
- Extensive examples and guidelines
- Multiple sections with detailed explanations

**Moderately Detailed (AI Engineer Agent):**
- 200+ lines with templating
- Structured sections with examples
- Conditional content based on context

**Minimal (Simple Agents):**
- 1-3 sentences
- Basic task description only
- No examples or guidelines

### 8. Inconsistent Error Handling and Edge Cases

**Comprehensive (Meta Agent):**
- Handles multiple user intent statuses
- Defines error scenarios
- Provides fallback behaviors

**Basic (Most Agents):**
- Simple task completion
- No error handling guidance
- No edge case considerations

## Side-by-Side Comparison of Agent Patterns

### Simple Agent vs Complex Agent

**Simple Agent (describe_images.py):**
```python
@workflowai.agent(id="describe-images-with-context", model=Model.GEMINI_1_5_FLASH_002)
async def describe_images_with_context(
    input: DescribeImagesWithContextTaskInput,
) -> DescribeImagesWithContextTaskOutput:
    """For each image in the input array, provide a detailed description tailored to the provided instructions."""
    ...
```

**Complex Agent (meta_agent.py):**
```python
META_AGENT_INSTRUCTIONS = """You are WorkflowAI's meta-agent. You are responsible for...

# Improving agents: concepts and common issues in agents
Several factors impact an agent behaviour and performance...

## Agent's schema:
Defines the shape of the input and output...

[300+ lines of detailed instructions]
"""

@workflowai.agent(
    version=workflowai.VersionProperties(
        instructions=META_AGENT_INSTRUCTIONS,
        model=workflowai.Model.CLAUDE_3_7_SONNET_20250219,
        temperature=0.5,
        max_tokens=1000,
    ),
)
```

## Specific Examples of Inconsistencies

### Example 1: Function Naming Patterns
- `run_improve_prompt_agent` (verb + noun + agent)
- `agent_name_suggestion_agent` (noun + noun + agent)
- `meta_agent` (adjective + agent)
- `suggest_model` (verb + noun)
- `company_context_agent` (noun + noun + agent)

### Example 2: Import and Setup Patterns
Some agents use `workflowai` imports:
```python
import workflowai
@workflowai.agent(...)
```

Others use direct model imports:
```python
from workflowai import Model
@workflowai.agent(model=Model.GEMINI_2_0_FLASH_001)
```

Others use OpenAI clients directly:
```python
from openai import AsyncOpenAI
client = AsyncOpenAI(...)
```

### Example 3: Response Format Handling
- Some agents use structured output with `response_format`
- Others rely on docstring instructions
- Some use Pydantic models implicitly
- Others handle JSON parsing manually

## Impact Assessment

### High Impact Issues
1. **Developer Confusion**: Inconsistent patterns make it difficult for developers to know which approach to follow
2. **Maintenance Overhead**: Multiple patterns require more cognitive load to maintain
3. **Quality Variance**: Different prompt styles lead to varying agent performance

### Medium Impact Issues
1. **Code Duplication**: Similar functionality implemented differently across agents
2. **Inconsistent User Experience**: Agents behave differently due to prompt style differences
3. **Onboarding Difficulty**: New developers face steep learning curve

### Low Impact Issues
1. **Cosmetic Inconsistencies**: Minor formatting differences
2. **Legacy Naming**: Some historical naming conventions still present

## Recommendations

### 1. Establish Prompt Standards
- Define standard prompt structure with required sections
- Create prompt templates for different agent types (simple, complex, interactive)
- Establish consistent terminology (use "instructions" vs "prompts")

### 2. Standardize Configuration Patterns
- Use `VersionProperties` consistently for all agents
- Standardize model reference patterns
- Define consistent import patterns

### 3. Create Prompt Guidelines
- Define when to use templating vs static prompts
- Establish style guide for tone and voice
- Create examples for different complexity levels

### 4. Implement Tooling
- Create linting rules for prompt consistency
- Develop prompt validation tools
- Add automated checks for naming conventions

### 5. Migration Strategy
- Priority 1: Fix high-impact inconsistencies (naming, structure)
- Priority 2: Standardize configuration patterns
- Priority 3: Align style and tone across all agents

## Conclusion

The analysis reveals significant inconsistencies across internal agents that impact maintainability, developer experience, and potentially agent performance. A systematic approach to standardization is recommended, starting with the highest-impact issues and gradually addressing all identified inconsistencies.