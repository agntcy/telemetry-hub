# Transformers Test Suite

## Overview

Test coverage for session transformers and enrichers - components that extract and compute derived data from sessions.

**Tests:** 25 tests
**Coverage:** ~70-75% (priority transformers)
**Execution Time:** ~0.09s

## Components Tested

- Base transformer classes (`DataTransformer`, `DataPreservingTransformer`, `DataPipeline`)
- `AgentTransitionTransformer` - Agent A → B transitions
- `ConversationDataTransformer` - Conversation extraction from LLM/agent spans
- `WorkflowDataTransformer` - Workflow patterns and query/response
- `ExecutionTreeTransformer` - Hierarchical execution tree
- `EndToEndAttributesTransformer` - Input query and final response

## Test Classes

### TestBaseTransformers (4 tests)
- Data preservation on first/subsequent calls
- Pipeline validation
- Transformer execution order

### TestAgentTransitionTransformer (3 tests)
- Transition extraction (A → B → C)
- Empty transitions handling
- Same agent repeated (no transition)

### TestConversationDataTransformer (6 tests)
- Extraction from LLM spans
- Element counting
- Tool call extraction
- Timestamp-based sorting
- Empty conversation handling

### TestWorkflowDataTransformer (6 tests)
- Workflow data extraction
- Query/response extraction
- Multiple workflows
- Error tracking
- Empty workflow handling

### TestExecutionTreeTransformer (2 tests)
- Tree building from parent-child relationships
- Empty session handling

### TestEndToEndAttributesTransformer (2 tests)
- Input query and final response extraction
- No LLM spans handling

### TestTransformerIntegration (4 tests)
- Full enrichment pipeline
- Chained transformer data preservation
- Invalid input handling
- Complete session enrichment

## Running Tests

```bash
uv run pytest src/metrics_computation_engine/tests/test_transformers.py -v
```

## Key Features

- Tests priority transformers (80/20 rule)
- Validates data preservation through pipeline
- Tests enrichment pipeline integration
- Fast execution
