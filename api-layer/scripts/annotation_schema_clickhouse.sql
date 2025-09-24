CREATE TABLE IF NOT EXISTS annotation_types (
    id String DEFAULT generateUUIDv4(),
    name String,
    type String,
    numerical_min Nullable(Float64),
    numerical_max Nullable(Float64),
    categorical_list Array(String),
    discontinued UInt8 DEFAULT 0,
    comment Nullable(String),
    creation_date DateTime DEFAULT now(),
    update_date DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(creation_date)
ORDER BY name
PRIMARY KEY name;

CREATE TABLE IF NOT EXISTS annotation_groups (
    id String DEFAULT generateUUIDv4(),
    annotation_type_ids Array(String),
    name String,
    min_reviews UInt32,
    max_reviews UInt32,
    max_report UInt32 DEFAULT 5,
    discontinued UInt8 DEFAULT 0,
    comment Nullable(String),
    creation_date DateTime DEFAULT now(),
    update_date DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(creation_date)
ORDER BY name
PRIMARY KEY name;

CREATE TABLE IF NOT EXISTS annotations (
    id String DEFAULT generateUUIDv4(),
    annotation_type_id String,
    group_item_id String,
    reviewer_id String,
    observation_id String,
    observation_type Enum8('session' = 1, 'trace' = 2, 'span' = 3),
    observation_kind String,
    session_id String,
    input String,
    input_type String,
    output String,
    output_type String,
    expected_output String,
    annotation_value String,
    acceptance_id Nullable(String),
    acceptance_date Nullable(DateTime),
    acceptance Nullable(UInt8),
    comment Nullable(String),
    creation_date DateTime DEFAULT now(),
    update_date DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(creation_date)
ORDER BY (reviewer_id, observation_id, annotation_type_id, creation_date)
PRIMARY KEY (reviewer_id, observation_id, annotation_type_id);

CREATE TABLE IF NOT EXISTS annotation_group_items (
    id String DEFAULT generateUUIDv4(),
    group_id String,
    session_id String,
    creation_date DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (group_id, session_id)
PRIMARY KEY (group_id, session_id);

CREATE TABLE IF NOT EXISTS annotation_consensus (
    id String DEFAULT generateUUIDv4(),
    group_id String,
    valid UInt8,
    quality_score Float64,
    annotation_statistics String,
    annotation_type_statistics String,
    consensus_values String,
    no_consensus_values String,
    reviewers_quality_score String,
    reviewers_stats String,
    method Enum8('majority' = 1) DEFAULT 'majority',
    creation_date DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (group_id, creation_date)
PRIMARY KEY (group_id, creation_date);

CREATE TABLE IF NOT EXISTS annotation_datasets (
    id String DEFAULT generateUUIDv4(),
    name String,
    tags Array(String),
    creation_date DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(creation_date)
ORDER BY name
PRIMARY KEY name;

CREATE TABLE IF NOT EXISTS annotation_dataset_items (
    id String DEFAULT generateUUIDv4(),
    dataset_id String,
    session_id String,
    session_date Nullable(DateTime),
    input String,
    output String,
    expected_output String,
    tags Array(String),
    creation_date DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(creation_date)
ORDER BY (dataset_id, session_id, creation_date)
PRIMARY KEY (dataset_id, session_id);