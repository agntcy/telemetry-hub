# Entities Module - Data Parsing Flow

This module handles the transformation of raw trace data into structured entities for analysis. It follows a multi-stage pipeline that processes OpenTelemetry traces into meaningful business objects.

## Overview

The entities module is responsible for:
1. **Parsing** raw trace data into structured span entities
2. **Aggregating** spans into sessions
3. **Enriching** sessions with execution trees and statistics
4. **Providing** standardized data models for analysis

## Architecture

```
Raw Traces → SpanEntity → SessionEntity → SessionSet → Statistics
```

### Core Components

#### 1. Data Parser (`core/data_parser.py`)
**Entry Point**: `parse_raw_spans(raw_spans: List[Dict]) -> List[SpanEntity]`

Transforms raw OpenTelemetry trace data into structured `SpanEntity` objects:

- **Entity Type Detection**: Classifies spans as `agent`, `tool`, `llm`, `workflow`, `graph`, or `task` based on span names and attributes
- **Multi-Framework Support**: Handles different AI frameworks (LangChain, LangGraph, Autogen) with specific detection patterns
- **Payload Processing**: Extracts input/output data, tool definitions, and metadata from span attributes
- **Error Detection**: Identifies spans containing errors for analysis

**Key Features**:
- Vectorized operations using pandas for performance
- Framework-specific entity name extraction (e.g., Autogen agent names from span patterns)
- Attribute-based payload processing with configurable extraction rules

#### 2. Session Aggregator (`core/session_aggregator.py`)
**Entry Point**: `aggregate_spans_to_sessions(spans: List[SpanEntity]) -> SessionSet`

Groups related spans into logical sessions:

- **Session Grouping**: Uses `session_id` or `execution_id` to group spans
- **Temporal Ordering**: Sorts spans by timestamp within sessions
- **Duration Calculation**: Computes session duration from earliest start to latest end time
- **Validation**: Ensures data consistency across session spans

#### 3. Session Enrichment (`transformers/session_enrichers.py`)
Enhances sessions with derived data:

- **Execution Tree**: Builds hierarchical relationships between spans using parent-child links
- **Agent Statistics**: Calculates per-agent metrics (LLM calls, tokens, duration, etc.)
- **Error Analysis**: Identifies and categorizes errors within sessions

## Data Models

### SpanEntity (`models/span.py`)
Core unit representing a single trace span:
```python
entity_type: "agent" | "tool" | "llm" | "workflow" | "graph" | "task"
span_id: str
entity_name: str
input_payload: Dict[str, Any]
output_payload: Dict[str, Any]
duration: float  # milliseconds
parent_span_id: Optional[str]
# ... additional metadata
```

### SessionEntity (`models/session.py`)
Represents a complete execution session:
```python
session_id: str
spans: List[SpanEntity]
execution_tree: List[SpanNode]  # Hierarchical view
agent_stats: Dict[str, AgentStats]  # Per-agent metrics
start_time: datetime
end_time: datetime
duration: float
```

### SessionSet (`models/session_set.py`)
Collection of sessions with aggregate statistics:
```python
sessions: List[SessionEntity]
stats: SessionSetStats  # Aggregate/histogram/meta statistics
```

## Processing Pipeline

### 1. Raw Data → Spans
```python
from poirot.entities.core.data_parser import parse_raw_spans

# Input: List of OpenTelemetry trace dictionaries
raw_traces = [{"SpanName": "...", "Attributes": {...}, ...}, ...]

# Output: Structured span entities
spans = parse_raw_spans(raw_traces)
```

### 2. Spans → Sessions
```python
from poirot.entities.core.session_aggregator import SessionAggregator

aggregator = SessionAggregator()
session_set = aggregator.aggregate_spans_to_sessions(spans)
```

### 3. Session Enhancement
Sessions are automatically enriched with:
- **Execution trees** showing span hierarchies
- **Agent statistics** for performance analysis
- **Error summaries** for debugging

## Framework Support

### LangChain/LangGraph
- Detects spans with `traceloop.entity.name` attributes
- Extracts tool definitions from LLM spans
- Handles workflow and agent patterns

### Autogen
- Detects spans with `autogen process` and `autogen create` patterns
- Extracts agent names from span names (e.g., `MultimodalWebSurfer` from `autogen process MultimodalWebSurfer_...`)
- Supports group chat managers and individual agents

### Custom Frameworks
New frameworks can be supported by:
1. Adding detection patterns in `data_parser.py`
2. Configuring payload extraction rules in `PAYLOAD_CONFIG`
3. Implementing framework-specific name extraction logic

## Statistics and Analysis

### Agent-Level Metrics
- LLM calls and token usage
- Tool calls and success rates
- Duration and performance metrics
- Error rates and types

### Session-Level Metrics
- Total execution time
- Resource utilization
- Success/failure rates
- Workflow complexity metrics

### Aggregate Statistics
- Cross-session averages and distributions
- Performance benchmarks
- Error pattern analysis

## Extension Points

### Adding New Entity Types
1. Update `SpanEntity.entity_type` literal type
2. Add detection logic in `data_parser.py`
3. Configure payload processing rules
4. Update statistics calculations if needed

### Custom Enrichment
1. Implement enrichers in `transformers/session_enrichers.py`
2. Add new computed properties to session models
3. Update statistics aggregation logic

### Framework Integration
1. Add framework detection patterns
2. Implement framework-specific attribute mappings
3. Add custom name extraction logic
4. Test with framework-specific trace samples

## Usage Examples

### Basic Parsing
```python
# Parse raw traces into structured data
spans = parse_raw_spans(raw_traces)
session_set = SessionAggregator().aggregate_spans_to_sessions(spans)

# Access session data
for session in session_set.sessions:
    print(f"Session {session.session_id}: {len(session.spans)} spans")
    print(f"Agents: {list(session.agent_stats.keys())}")
```

### Statistics Analysis
```python
# Get comprehensive statistics
stats = session_set.stats

# Agent performance
for agent_name, agent_stats in stats.aggregate.agents.items():
    print(f"{agent_name}: {agent_stats.avg_llm_calls} avg LLM calls")

# Session metadata
for uuid, app_name in stats.meta.session_ids:
    print(f"App: {app_name}, Session: {uuid}")
```

## Performance Considerations

- **Pandas Optimization**: Uses vectorized operations for large datasets
- **Lazy Loading**: Statistics computed on-demand
- **Memory Efficiency**: Raw span data preserved only when needed
- **Caching**: Session enrichment results cached to avoid recomputation

For production use with large trace volumes, consider implementing streaming parsers and incremental aggregation strategies.
