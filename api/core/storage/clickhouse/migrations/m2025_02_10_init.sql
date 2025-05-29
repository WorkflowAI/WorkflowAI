-- File should be executed in Clickhouse directly

-- Enable async inserts to allow Clickhouse to buffer writes to disk
-- Since we will send writes 1 by 1 when a run is created
-- ALTER USER default SETTINGS async_insert = 1;

-- Main Run Table
CREATE TABLE runs (
    -- Tenant and task identifiers
    tenant_uid UInt32,
    task_uid UInt32,
    created_at_date Date,
    -- Not storing as a UUID directly, because UUIDs are not properly ordered
    -- https://clickhouse.com/docs/en/sql-reference/data-types/uuid
    run_uuid UInt128,

    -- Updated at
    updated_at DateTime,

    -- Task schema id
    task_schema_id UInt16,
    -- MD5 hash of version properties
    version_id FixedString(32),
    -- The version Iteration, this field is deprecated but used for backwards compatibility
    -- We should remove it in the future
    version_iteration UInt16,
    version_model LowCardinality(String),
    -- temperature * 100, stored as UInt8 to save space
    version_temperature_percent UInt8,

    -- Hashes
    input_hash FixedString(32),
    output_hash FixedString(32),
    eval_hash FixedString(32),
    cache_hash FixedString(32),

    -- IO
    input_preview String,
    input String,
    output_preview String,
    output String,

    -- Duration stored in tenth of a second, 0 is used as a default value
    -- and should be ignored in aggregations
    -- Maxes out at 65535 = 6555.35 seconds = 100.92 minutes
    duration_ds UInt16,
    -- Overhead is stored in milliseconds as a UInt8. This means
    -- That the max stored value is 255ms which is way more that what we should allow for latency
    -- Final value will g
    -- This field could be calculated from the duration_seconds of the llm_completions but it is not usable
    -- yet because of legacy data.
    overhead_ms UInt8,
    -- Cost stored in millionths of a USD, 0 is used as a default value
    -- and should be ignored in aggregations
    -- Other options would be:
    --  - storing as Nullable(Float32), but Float32 could lead to rounding errors
    --  - storing as Decimal(10,S), but since we can have runs that are very cheap, finding a good scale value
    --    would be difficult
    -- 
    cost_millionth_usd UInt32,
    -- Number of tokens used
    input_token_count UInt32,
    output_token_count UInt32,

    -- Status
    error_payload String,
    
    -- Metadata
    metadata Map(String, String),

    -- ProviderConfig
    provider_config_uuid UUID,

    -- Author UID
    author_uid UInt32,


    -- Whether the run is active, i-e created by the SDK/API
    is_active Boolean,

    -- Tool Calls
    tool_calls Array(String) CODEC(ZSTD(3)),
    
    -- Reasoning steps
    reasoning_steps Array(String),

    -- LLM completions
    llm_completions Array(String) CODEC(ZSTD(3)),
)
-- ReplacingMergeTree https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/replacingmergetree
-- De-duplicates data base on the ORDER_BY clause
-- updated_at is used as a versioning key, so that the latest
-- updated run takes precedence
ENGINE = ReplacingMergeTree(updated_at)
-- 
PARTITION BY toYYYYMM(created_at_date)
-- Composite primary key, needs to be sparse
PRIMARY KEY (tenant_uid, created_at_date, task_uid)
-- Order by run uuid allows finding runs by UUID fairly fast
ORDER BY (tenant_uid, created_at_date, task_uid, run_uuid);

-- Add a bloom filter index on the cache_hash, eval_hash and input_hash columns
-- For somewhat efficient retrieval
ALTER TABLE runs ADD INDEX cache_hash_index cache_hash TYPE bloom_filter(0.01);
ALTER TABLE runs ADD INDEX eval_hash_index eval_hash TYPE bloom_filter(0.01);
ALTER TABLE runs ADD INDEX input_hash_index input_hash TYPE bloom_filter(0.01);

ALTER TABLE runs ADD COLUMN conversation_id UInt128 DEFAULT reinterpretAsUInt128(generateUUIDv7());
