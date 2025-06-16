# Context Window Usage Percentage Storage Spec

## Overview

This spec outlines how to add context window usage percentage storage to ClickHouse for every run. Currently, we store `input_token_count` and `output_token_count` but querying for runs above a certain context window threshold (e.g., 80%) is difficult because the maximum token count is stored at the model level.

## Problem Statement

To query runs with context window usage above 80%, you would need to:
1. Join with model data to get max context window size
2. Calculate percentage: `(input_token_count + output_token_count) / model_context_window_size`
3. Filter by percentage

This is complex and inefficient for analytics queries.

## Solution

Add a new field `context_window_usage_percent` to store the pre-calculated percentage, making queries like "runs with >80% context usage" simple and fast.

## Implementation Plan

### 1. Database Schema Changes

#### 1.1 Migration File: `m2025_XX_XX_add_context_window_percentage.sql`

```sql
-- Add context window usage percentage field to runs table
-- Stored as UInt8 representing percentage (0-100)
-- 0 is used as default/null value when context window size is unknown
ALTER TABLE runs ADD COLUMN context_window_usage_percent UInt8 DEFAULT 0;
```

**Rationale for UInt8:**
- Range 0-255 is sufficient (we only need 0-100 for percentages)
- Consistent with existing fields like `version_temperature_percent`
- Space efficient (1 byte per row)
- 0 as default indicates unknown/unavailable context window data

#### 1.2 ClickhouseRun Model Updates

**File:** `api/core/storage/clickhouse/models/runs.py`

```python
class ClickhouseRun(BaseModel):
    # ... existing fields ...
    input_token_count: Annotated[int, validate_int(MAX_UINT_32, "input_token_count")] = 0
    output_token_count: Annotated[int, validate_int(MAX_UINT_32, "output_token_count")] = 0
    context_window_usage_percent: Annotated[int, validate_int(MAX_UINT_8, "context_window_usage_percent")] = 0
```

Add to `FIELD_TO_COLUMN` mapping:
```python
FIELD_TO_COLUMN: dict[SerializableTaskRunField, str] = {
    # ... existing mappings ...
    "context_window_usage_percent": "context_window_usage_percent",
}
```

Add to `_FIELD_TO_QUERY` for search support:
```python
_FIELD_TO_QUERY: dict[SearchField, tuple[str, str, Callable[[Any], Any] | None]] = {
    # ... existing mappings ...
    SearchField.CONTEXT_WINDOW_USAGE: ("context_window_usage_percent", "UInt8", None),
}
```

### 2. Calculation Logic

#### 2.1 Update `ClickhouseRun.from_domain()` method

```python
@classmethod
def from_domain(cls, tenant: int, run: AgentRun):
    # Calculate context window usage percentage
    context_window_usage_percent = cls._calculate_context_window_usage_percent(run)
    
    return cls(
        # ... existing fields ...
        input_token_count=run.input_token_count or 0,
        output_token_count=run.output_token_count or 0,
        context_window_usage_percent=context_window_usage_percent,
        # ... rest of fields ...
    )

@classmethod
def _calculate_context_window_usage_percent(cls, run: AgentRun) -> int:
    """
    Calculate context window usage percentage from run data.
    
    Returns:
        int: Percentage (0-100), or 0 if context window size is unavailable
    """
    input_tokens = run.input_token_count or 0
    output_tokens = run.output_token_count or 0
    total_tokens = input_tokens + output_tokens
    
    if total_tokens == 0:
        return 0
    
    # Get context window size from LLM completions
    context_window_size = cls._extract_context_window_size(run)
    
    if not context_window_size or context_window_size <= 0:
        return 0
    
    # Calculate percentage, capped at 100
    percentage = min(100, int((total_tokens / context_window_size) * 100))
    return percentage

@classmethod  
def _extract_context_window_size(cls, run: AgentRun) -> int | None:
    """
    Extract context window size from run's LLM completions.
    
    Prioritizes the first completion with a valid context window size.
    """
    if not run.llm_completions:
        return None
    
    for completion in run.llm_completions:
        if completion.usage and completion.usage.model_context_window_size:
            return completion.usage.model_context_window_size
    
    return None
```

### 3. Search and Query Support

#### 3.1 Add SearchField enum value

**File:** `api/core/domain/search_query.py`

```python
class SearchField(str, Enum):
    # ... existing fields ...
    CONTEXT_WINDOW_USAGE = "context_window_usage"
```

#### 3.2 Frontend integration

The field can be exposed to frontend queries for filtering runs by context window usage:

```typescript
// Example query: runs with >80% context window usage
const highContextUsageQuery = {
  field: 'context_window_usage',
  operation: {
    operator: 'greater_than',
    value: 80
  }
}
```

### 4. Backward Compatibility

#### 4.1 Existing Data Migration

For existing runs without context window percentage:

1. **Default value**: New field defaults to 0 (unknown)
2. **Backfill script**: Optional script to calculate percentages for existing runs using model data
3. **Graceful degradation**: Queries handle 0 values appropriately

#### 4.2 AgentRun Domain Model

**File:** `api/core/domain/agent_run.py`

Add optional field to maintain backward compatibility:

```python
@dataclass
class AgentRun:
    # ... existing fields ...
    context_window_usage_percent: int | None = None
```

Update `ClickhouseRun.to_domain()`:

```python
def to_domain(self, task_id: str) -> AgentRun:
    return AgentRun(
        # ... existing field mappings ...
        context_window_usage_percent=self.context_window_usage_percent if self.context_window_usage_percent > 0 else None,
        # ... rest of fields ...
    )
```

### 5. Testing

#### 5.1 Unit Tests

**File:** `api/core/storage/clickhouse/models/runs_test.py`

```python
def test_context_window_usage_calculation():
    """Test context window percentage calculation."""
    run = task_run_ser(
        id=str(uuid7()),
        task_uid=1,
        input_token_count=800,
        output_token_count=200,
        llm_completions=[
            LLMCompletion(
                messages=[{"role": "user", "content": "test"}],
                usage=LLMUsage(
                    prompt_token_count=800,
                    completion_token_count=200,
                    model_context_window_size=1000
                ),
                provider=Provider.OPEN_AI,
            )
        ]
    )
    
    clickhouse_run = ClickhouseRun.from_domain(1, run)
    assert clickhouse_run.context_window_usage_percent == 100  # (800+200)/1000 * 100

def test_context_window_usage_unknown():
    """Test context window percentage when size is unknown."""
    run = task_run_ser(
        id=str(uuid7()),
        task_uid=1,
        input_token_count=800,
        output_token_count=200,
        llm_completions=[]  # No completions = no context window size
    )
    
    clickhouse_run = ClickhouseRun.from_domain(1, run)
    assert clickhouse_run.context_window_usage_percent == 0
```

#### 5.2 Integration Tests

**File:** `api/core/storage/clickhouse/clickhouse_client_test.py`

```python
async def test_search_by_context_window_usage(clickhouse_client: ClickhouseClient):
    """Test filtering runs by context window usage percentage."""
    runs = [
        _ck_run(context_window_usage_percent=90),  # High usage
        _ck_run(context_window_usage_percent=50),  # Medium usage  
        _ck_run(context_window_usage_percent=0),   # Unknown usage
    ]
    
    await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})
    
    # Query for runs with >80% context usage
    search_query = SearchQuerySimple(
        SearchField.CONTEXT_WINDOW_USAGE,
        SearchOperationSingle(SearchOperator.GREATER_THAN, 80)
    )
    
    results = await clickhouse_client._search(("test", 1), [search_query])
    assert len(results) == 1  # Only the 90% usage run
```

### 6. Analytics Benefits

With this implementation, analytics queries become simple:

```sql
-- Runs with >80% context window usage
SELECT COUNT(*) 
FROM runs 
WHERE context_window_usage_percent > 80;

-- Average context window usage by model
SELECT 
    version_model,
    AVG(context_window_usage_percent) as avg_usage
FROM runs 
WHERE context_window_usage_percent > 0  -- Exclude unknown values
GROUP BY version_model;

-- Context window usage distribution
SELECT 
    CASE 
        WHEN context_window_usage_percent = 0 THEN 'Unknown'
        WHEN context_window_usage_percent <= 50 THEN 'Low (≤50%)'
        WHEN context_window_usage_percent <= 80 THEN 'Medium (51-80%)'
        ELSE 'High (>80%)'
    END as usage_category,
    COUNT(*) as run_count
FROM runs
GROUP BY usage_category;
```

### 7. Performance Considerations

- **Storage**: +1 byte per run (minimal impact)
- **Index**: Consider adding index if frequent filtering by context usage
- **Calculation**: O(1) calculation during run storage (minimal overhead)
- **Query performance**: Direct field access vs complex joins with model data

### 8. Future Enhancements

1. **Alerting**: Monitor runs approaching context limits
2. **Automatic model selection**: Route to larger context models when usage is high
3. **Cost optimization**: Track correlation between context usage and costs
4. **Usage trends**: Analyze context usage patterns over time

## Migration Path

1. **Phase 1**: Add database column with migration
2. **Phase 2**: Update ClickhouseRun model to calculate and store percentage
3. **Phase 3**: Add search/query support
4. **Phase 4**: Optional backfill of existing data
5. **Phase 5**: Frontend integration for filtering and analytics

This approach provides immediate value for new runs while maintaining backward compatibility with existing data.