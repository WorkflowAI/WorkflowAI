# MCP ClickHouse Query Tool Specification

## Overview

This specification outlines the design and implementation of a Model Context Protocol (MCP) tool that enables read-only SQL queries on our ClickHouse database containing agent run statistics. The tool provides flexible access to performance metrics, cost analysis, and operational insights for agents and tenants.

## Benefits

### 1. **Flexible Analytics**
- Enable custom queries for specific business intelligence needs
- Support ad-hoc analysis without requiring backend code changes
- Allow complex aggregations and filtering across multiple dimensions

### 2. **Self-Service Analytics**
- Reduce dependency on engineering team for data requests
- Enable product managers and analysts to extract insights independently
- Support rapid prototyping of new metrics and dashboards

### 3. **Enhanced Observability**
- Provide deep insights into agent performance patterns
- Enable cost optimization through detailed usage analysis
- Support troubleshooting with granular run data

### 4. **Tenant Isolation**
- Ensure data access is properly scoped to tenant boundaries
- Maintain security while providing analytical flexibility
- Support multi-tenant analysis where appropriate

## Use Cases and Example Queries

### 1. Cost Analysis

#### Total cost for all agents in the last week
```sql
SELECT 
    SUM(cost_millionth_usd) / 1000000.0 AS total_cost_usd,
    COUNT(*) AS total_runs
FROM runs 
WHERE tenant_uid = {tenant_uid}
    AND created_at_date >= today() - INTERVAL 7 DAY
    AND cost_millionth_usd > 0;
```

#### Cost for specific agent aggregated by day in the last week
```sql
SELECT 
    created_at_date,
    SUM(cost_millionth_usd) / 1000000.0 AS daily_cost_usd,
    COUNT(*) AS daily_runs
FROM runs 
WHERE tenant_uid = {tenant_uid}
    AND task_uid = {agent_id}
    AND created_at_date >= today() - INTERVAL 7 DAY
    AND cost_millionth_usd > 0
GROUP BY created_at_date
ORDER BY created_at_date;
```

#### Cost for specific agent aggregated by week in the last 4 weeks
```sql
SELECT 
    toStartOfWeek(created_at_date) AS week_start,
    SUM(cost_millionth_usd) / 1000000.0 AS weekly_cost_usd,
    COUNT(*) AS weekly_runs
FROM runs 
WHERE tenant_uid = {tenant_uid}
    AND task_uid = {agent_id}
    AND created_at_date >= today() - INTERVAL 28 DAY
    AND cost_millionth_usd > 0
GROUP BY week_start
ORDER BY week_start;
```

### 2. Performance Analysis

#### Average latency for a specific agent
```sql
SELECT 
    AVG(duration_ds) / 10.0 AS avg_latency_seconds,
    AVG(overhead_ms) AS avg_overhead_ms,
    PERCENTILE(duration_ds / 10.0, 0.5) AS median_latency_seconds,
    PERCENTILE(duration_ds / 10.0, 0.95) AS p95_latency_seconds
FROM runs 
WHERE tenant_uid = {tenant_uid}
    AND task_uid = {agent_id}
    AND duration_ds > 0
    AND error_payload = '';
```

#### Performance trends by model
```sql
SELECT 
    version_model,
    AVG(duration_ds) / 10.0 AS avg_latency_seconds,
    SUM(cost_millionth_usd) / 1000000.0 AS total_cost_usd,
    COUNT(*) AS run_count
FROM runs 
WHERE tenant_uid = {tenant_uid}
    AND created_at_date >= today() - INTERVAL 7 DAY
    AND duration_ds > 0
GROUP BY version_model
ORDER BY run_count DESC;
```

### 3. Error Analysis

#### Error rate by agent
```sql
SELECT 
    task_uid,
    COUNT(*) AS total_runs,
    SUM(CASE WHEN error_payload != '' THEN 1 ELSE 0 END) AS error_count,
    (SUM(CASE WHEN error_payload != '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS error_rate_percent
FROM runs 
WHERE tenant_uid = {tenant_uid}
    AND created_at_date >= today() - INTERVAL 7 DAY
GROUP BY task_uid
HAVING total_runs > 10
ORDER BY error_rate_percent DESC;
```

### 4. Token Usage Analysis

#### Token consumption by agent
```sql
SELECT 
    task_uid,
    SUM(input_token_count) AS total_input_tokens,
    SUM(output_token_count) AS total_output_tokens,
    AVG(input_token_count) AS avg_input_tokens,
    AVG(output_token_count) AS avg_output_tokens
FROM runs 
WHERE tenant_uid = {tenant_uid}
    AND created_at_date >= today() - INTERVAL 7 DAY
    AND error_payload = ''
GROUP BY task_uid
ORDER BY total_input_tokens + total_output_tokens DESC;
```

### 5. Metadata Analysis

#### Usage patterns by metadata fields
```sql
SELECT 
    metadata['environment'] AS environment,
    metadata['version'] AS version,
    COUNT(*) AS run_count,
    AVG(duration_ds) / 10.0 AS avg_latency_seconds
FROM runs 
WHERE tenant_uid = {tenant_uid}
    AND created_at_date >= today() - INTERVAL 7 DAY
    AND metadata['environment'] != ''
GROUP BY metadata['environment'], metadata['version']
ORDER BY run_count DESC;
```

## Implementation Design

### 1. MCP Tool Interface

```python
class ClickHouseQueryTool:
    name = "clickhouse_query"
    description = "Execute read-only SQL queries on ClickHouse runs database"
    
    def __init__(self, tenant_uid: int, connection_string: str):
        self.tenant_uid = tenant_uid
        self.connection_string = connection_string
    
    async def execute(self, query: str, parameters: dict = None) -> QueryResult:
        """Execute a read-only SQL query with tenant isolation"""
        pass
```

### 2. Query Processing Pipeline

```
User Query → Validation → Tenant Injection → Execution → Result Formatting
```

#### Validation Steps:
1. **SQL Syntax Validation**: Ensure query is valid SQL
2. **Read-Only Enforcement**: Block INSERT, UPDATE, DELETE, CREATE, DROP operations
3. **Table Restriction**: Only allow queries on the `runs` table
4. **Tenant Isolation**: Automatically inject tenant_uid filter

#### Tenant Injection:
- Automatically add `WHERE tenant_uid = {tenant_uid}` to all queries
- Parse the query AST to insert the condition in the appropriate location
- Handle complex queries with JOINs, subqueries, and CTEs

### 3. Security Considerations

#### Query Restrictions:
- **Read-Only**: Only SELECT statements allowed
- **Table Whitelist**: Only `runs` table accessible
- **No System Tables**: Block access to system.* tables
- **Resource Limits**: Set timeouts and row limits

#### Tenant Isolation:
- Automatically inject tenant_uid filter in all queries
- Validate that user has access to the specified tenant
- Log all queries for audit purposes

#### Input Sanitization:
- Use parameterized queries where possible
- Validate and sanitize all user inputs
- Implement query complexity limits

### 4. API Design

#### Input Schema:
```json
{
  "tool": "clickhouse_query",
  "parameters": {
    "query": "SELECT COUNT(*) FROM runs WHERE created_at_date >= today() - INTERVAL 7 DAY"
  }
}
```

#### Output Schema:
```json
{
  "success": true,
  "data": {
    "columns": ["count"],
    "rows": [[1234]],
    "execution_time_ms": 45,
    "rows_returned": 1
  },
  "metadata": {
    "tenant_uid": 123,
    "executed_at": "2025-01-09T10:30:00Z"
  }
}
```

### 5. Implementation Components

#### Core Components:
1. **QueryValidator**: Validates SQL syntax and restrictions
2. **TenantInjector**: Automatically adds tenant filtering
3. **QueryExecutor**: Executes queries against ClickHouse
4. **ResultFormatter**: Formats results for MCP response
5. **AuditLogger**: Logs all queries for monitoring

#### Configuration:
- Default query timeout limits configured at service level
- Allowed query complexity limits
- Rate limiting per tenant

## Monitoring and Observability

### Metrics to Track:
- Query execution time
- Query frequency per tenant
- Failed query rate
- Resource usage (memory, CPU)
- Popular query patterns

### Logging:
- All executed queries with tenant context
- Query performance metrics
- Security violations and blocked queries
- Error rates and failure reasons

## Future Enhancements

### Query Optimization:
- Query result caching for common patterns
- Query plan analysis and optimization suggestions
- Automatic query rewriting for better performance

### Advanced Features:
- Saved queries and query templates
- Query scheduling and automation
- Integration with visualization tools
- Query sharing and collaboration features

### Schema Evolution:
- Support for additional tables as they become available
- Dynamic schema discovery and documentation
- Version-aware query compatibility

## Security Review Checklist

- [ ] SQL injection prevention
- [ ] Tenant isolation enforcement
- [ ] Read-only access verification
- [ ] Resource limit implementation
- [ ] Audit logging setup
- [ ] Rate limiting configuration
- [ ] Error message sanitization
- [ ] Query complexity limits
- [ ] Timeout enforcement
- [ ] Input validation coverage

## Conclusion

The MCP ClickHouse Query Tool provides a powerful, secure, and flexible way to access agent run analytics. By combining the flexibility of SQL with proper security controls and tenant isolation, this tool enables self-service analytics while maintaining data integrity and security.

The implementation focuses on safety-first design with comprehensive validation, automatic tenant filtering, and extensive monitoring. This approach ensures that users can access the insights they need while maintaining the security and reliability of the system.