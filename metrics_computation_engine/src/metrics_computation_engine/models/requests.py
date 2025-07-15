# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional

from pydantic import BaseModel


class LLMJudgeConfig(BaseModel):
    LLM_BASE_MODEL_URL: str = "https://api.openai.com/v1"
    LLM_MODEL_NAME: str = "gpt-4o"
    LLM_API_KEY: str = "sk-..."

    
class BatchTimeRange(BaseModel):
    start: str
    end: str


class BatchConfig(BaseModel):
    time_range: Optional[BatchTimeRange] = None
    num_sessions: Optional[int] = 1
    app_name: Optional[str] = None


class MetricsConfigRequest(BaseModel):
    metrics: List[str] = ["AgentToToolInteractions", "ToolUtilizationAccuracy"]
    llm_judge_config: LLMJudgeConfig = LLMJudgeConfig()
    batch_config: BatchConfig = BatchConfig()
