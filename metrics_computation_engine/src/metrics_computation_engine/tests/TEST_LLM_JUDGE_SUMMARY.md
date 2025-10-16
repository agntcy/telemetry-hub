# LLM Judge Test Suite

## Overview

Test coverage for the LLM Judge system (`llm_judge/` module) - responsible for LLM-as-a-judge metric evaluations.

**Tests:** 23 tests
**Coverage:** ~90%
**Execution Time:** ~0.10s

## Components Tested

- `jury.py` - Judge orchestration and consensus
- `llm.py` - LLM client wrapper
- `utils/response_parsing.py` - Response parsing utilities
- `prompts.py` - System prompts

## Test Classes

### TestResponseParsing (6 tests)
- JSON parsing with markdown code blocks
- Python dict string parsing (ast.literal_eval fallback)
- Nested dictionary key extraction
- Error handling for invalid inputs

### TestLLMClient (4 tests)
- Configuration initialization
- Provider detection (OpenAI vs custom)
- Query execution (mocked litellm)

### TestJury (6 tests)
- Single and multi-model initialization
- Prompt augmentation with Pydantic schemas
- Consensus score calculation
- Full judge workflow (mocked)

### TestLLMJudgeIntegration (3 tests)
- End-to-end judge workflow
- Multi-model consensus
- Structured output generation

### TestLLMJudgeEdgeCases (4 tests)
- Deep nesting, lists of dicts
- Whitespace handling
- Complex JSON structures

## Running Tests

```bash
# All LLM Judge tests
uv run pytest src/metrics_computation_engine/tests/test_llm_judge.py -v

# Specific test class
uv run pytest src/metrics_computation_engine/tests/test_llm_judge.py::TestJury -v
```

## Key Features

- All LLM API calls mocked (no costs)
- Deterministic test execution
- Fast feedback (<0.1s)
- Protects 11 plugin metrics that use LLM-as-judge
