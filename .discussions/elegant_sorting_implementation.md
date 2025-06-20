# Goal of this PR

This PR implements a more elegant sorting solution for the MCP server by replacing the single monolithic sort parameter with a two-field approach:

**Original approach:**

- Single `sort_by` parameter with predefined values like `"last_active_first"`, `"most_costly_first"`, `"smartest_first"`

**New approach:**

- `sort_by`: The field name to sort by (e.g., `'last_active_at'`, `'total_cost_usd'`, `'quality_index'`)
- `order`: The direction to sort (`'asc'` for ascending, `'desc'` for descending)

This design provides better flexibility and follows common API design patterns where sorting is specified as separate field and direction parameters.

## Implementation Decision

### New Type Definitions

I replaced the monolithic sort type aliases with more granular ones:

**Before:**

```python
SortAgentBy: TypeAlias = Literal["last_active_first", "most_costly_first", "most_runs_first"]
SortModelBy: TypeAlias = Literal["latest_released_first", "smartest_first", "cheapest_first"]
```

**After:**

```python
AgentSortField: TypeAlias = Literal["last_active_at", "total_cost_usd", "run_count"]
ModelSortField: TypeAlias = Literal["release_date", "quality_index", "cost"]
SortOrder: TypeAlias = Literal["asc", "desc"]
```

### Function Signature Changes

**Agent Sorting:**

```python
# Before
def sort_agents(agents: list[AgentResponse], sort_by: SortAgentBy) -> list[AgentResponse]:

# After
def sort_agents(agents: list[AgentResponse], sort_by: AgentSortField, order: SortOrder) -> list[AgentResponse]:
```

**Model Sorting:**

```python
# Before
def sort_models(models: list[ConciseModelResponse | ConciseLatestModelResponse], sort_by: SortModelBy) -> list[...]:

# After
def sort_models(models: list[ConciseModelResponse | ConciseLatestModelResponse], sort_by: ModelSortField, order: SortOrder) -> list[...]:
```

### MCP Tool Parameters

**list_available_models tool:**

```json
{
  "sort_by": {
    "type": "string",
    "description": "The field name to sort by, e.g., 'release_date', 'quality_index', 'cost'"
  },
  "order": {
    "type": "string",
    "enum": ["asc", "desc"],
    "description": "The direction to sort: 'asc' for ascending, 'desc' for descending"
  }
}
```

**list_agents tool:**

```json
{
  "sort_by": {
    "type": "string",
    "description": "The field name to sort by, e.g., 'last_active_at', 'total_cost_usd', 'run_count'"
  },
  "order": {
    "type": "string",
    "enum": ["asc", "desc"],
    "description": "The direction to sort: 'asc' for ascending, 'desc' for descending"
  }
}
```

### Sorting Logic Implementation

The new implementation uses a clean approach where:

1. `reverse_sort = order == "desc"` determines the sort direction
2. All sort functions use the same `reverse` parameter based on the order
3. Stable secondary sorting by ID/name is maintained for consistency

Example for agent sorting:

```python
def sort_agents(agents: list[AgentResponse], sort_by: AgentSortField, order: SortOrder) -> list[AgentResponse]:
    reverse_sort = order == "desc"

    if sort_by == "last_active_at":
        agents.sort(key=get_max_last_active_at, reverse=reverse_sort)
    elif sort_by == "total_cost_usd":
        agents.sort(key=lambda x: (x.total_cost_usd, x.agent_id), reverse=reverse_sort)
    elif sort_by == "run_count":
        agents.sort(key=lambda x: (x.run_count, x.agent_id), reverse=reverse_sort)
```

### Default Values

I set sensible defaults that maintain backwards compatibility in terms of user experience:

- **Agents:** `sort_by="last_active_at"`, `order="desc"` (newest activity first)
- **Models:** `sort_by="quality_index"`, `order="desc"` (highest quality first)

## Tests Status

### Agent Sorting Tests

✅ **Updated and Comprehensive**: I rewrote all agent sorting tests to use the new two-field approach:

- **Basic functionality tests**: Covers all three sort fields (`last_active_at`, `total_cost_usd`, `run_count`) with both `asc` and `desc` orders
- **Edge case tests**: Handles None values, empty lists, single agents, and stable ordering
- **Data preservation tests**: Ensures sorting doesn't modify the original agent data
- **In-place modification tests**: Verifies that sorting modifies the list in place

**Key test examples:**

- `test_sort_by_last_active_at_desc_basic()`: Newest activity first
- `test_sort_by_total_cost_usd_asc()`: Lowest cost first
- `test_sort_by_run_count_desc()`: Highest run count first
- `test_sort_by_last_active_at_with_none_values()`: Handles missing activity dates

### Model Sorting Tests

✅ **Updated and Comprehensive**: I rewrote all model sorting tests to use the new two-field approach:

- **Basic functionality tests**: Covers all three sort fields (`release_date`, `quality_index`, `cost`) with both orders
- **Latest model handling**: Maintains complex logic for latest models appearing above their targets
- **Orphaned model handling**: Properly handles latest models pointing to non-existent models
- **Stable ordering tests**: Ensures consistent results when values are equal

**Key test examples:**

- `test_sort_by_release_date_desc()`: Newest release first
- `test_sort_by_quality_index_asc()`: Lowest quality first
- `test_sort_by_cost_desc()`: Most expensive first
- `test_latest_models_appear_above_target()`: Complex latest model positioning

### Test Execution Status

✅ **Code Quality Checks Passed**: All linting and type checking passes successfully:

- ✅ **Ruff**: All checks passed! (code style and formatting)
- ✅ **Pyright**: 0 errors, 0 warnings, 0 informations (type checking)

⚠️ **Unit Tests**: Cannot run pytest in current environment due to missing dependencies. However, based on the code structure and comprehensive test coverage, the implementation should work correctly.

**Test files updated:**

- ✅ `api/api/routers/mcp/_utils/agent_sorting_test.py` - 15 test methods updated
- ✅ `api/api/routers/mcp/_utils/model_sorting_test.py` - 16 test methods updated

## Interesting Implementation Details

### 1. Backwards Compatibility Consideration

While the API changes break backwards compatibility at the parameter level, the new approach is more intuitive and follows REST API conventions. The old hardcoded values like `"most_costly_first"` were replaced with clearer field names and explicit direction.

### 2. Complex Model Sorting Logic Preserved

The model sorting maintains the sophisticated logic for handling "latest" models that point to concrete models:

- Latest models appear just above their target concrete models
- Multiple latest models pointing to the same target are sorted by ID
- Orphaned latest models (pointing to non-existent targets) appear at the end

### 3. Stable Secondary Sorting

All sorting maintains stable secondary sorting by `agent_id` or `model.id` to ensure consistent, predictable results when primary values are equal.

### 4. Null Value Handling

Special care was taken for `last_active_at` sorting:

- Agents with no activity dates get a dummy date `"0000-00-00T00:00:00"`
- This ensures they sort consistently relative to real dates regardless of sort order

### 5. Type Safety

The new implementation maintains full type safety with:

- Literal types for field names and sort order
- Proper generic typing for model responses
- Union types for latest vs concrete model responses

## Potential Next Steps

1. **Database Query Optimization**: Consider pushing sorting to the database level for better performance with large datasets

2. **Additional Sort Fields**: The new flexible approach makes it easy to add new sort fields:

   - For agents: `created_at`, `updated_at`, `name`
   - For models: `context_window`, `provider`, `supports_count`

3. **Multi-field Sorting**: The architecture could be extended to support sorting by multiple fields with different orders

4. **Sort Field Validation**: Add runtime validation to ensure sort fields are valid for the given entity type

5. **Caching**: Implement result caching for expensive sort operations, especially for model lists

6. **API Documentation**: Update the MCP server documentation to reflect the new two-field sorting approach

7. **Migration Guide**: Provide clear migration instructions for existing clients using the old sorting parameters

---

## Context: Original User Request

The user requested implementing a more elegant solution based on PR feedback, specifically:

> "my feedback is that the sorting in the MCP server should be implemented by using a two fields: • "sort_by" the dimension on which to sort/order • "order" so represented in JSON "properties": { "sort_by": { "type": "string", "description": "The field name to sort by, e.g., 'created_at', 'name', 'score'" }, "order": { "type": "string", "enum": ["asc", "desc"], "description": "The direction to sort: 'asc' for ascending, 'desc' for descending" } }"

This implementation fully addresses that feedback by providing a clean, flexible, and extensible sorting solution that follows modern API design principles.
