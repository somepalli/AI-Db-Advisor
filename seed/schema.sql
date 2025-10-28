-- ClickHouse schema for AI DB Advisor demo dataset
-- Database name is templated and replaced by load_seed.sh

CREATE DATABASE IF NOT EXISTS {{CLICKHOUSE_DB}};

CREATE TABLE IF NOT EXISTS {{CLICKHOUSE_DB}}.users (
    user_id UInt32,
    email String,
    full_name String,
    signup_date Date,
    city LowCardinality(String),
    total_spent Decimal(12, 2),
    last_login DateTime
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(signup_date)
ORDER BY (signup_date, user_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS {{CLICKHOUSE_DB}}.orders (
    order_id UInt64,
    user_id UInt32,
    order_total Decimal(12, 2),
    status LowCardinality(String),
    created_at DateTime,
    fulfilled_at DateTime
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (user_id, created_at)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS {{CLICKHOUSE_DB}}.events (
    event_id UUID,
    user_id UInt32,
    order_id UInt64,
    event_type LowCardinality(String),
    source LowCardinality(String),
    occurred_at DateTime,
    details String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(occurred_at)
ORDER BY (occurred_at, user_id)
SETTINGS index_granularity = 8192;
