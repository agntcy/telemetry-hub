# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone


class LLMJudgeConfig(BaseModel):
    LLM_BASE_MODEL_URL: str = "https://api.openai.com/v1"
    LLM_MODEL_NAME: str = "gpt-5"
    LLM_API_KEY: str = "sk-..."
    NUM_LLM_RETRIES: int = 3


class BatchTimeRange(BaseModel):
    start: str  # Time in ISO 8601 UTC format (e.g. 2023-06-25T15:04:05Z)
    end: str  # Time in ISO 8601 UTC format (e.g. 2023-06-25T15:04:05Z)

    def get_start(self) -> str:
        return self.start

    def get_end(self) -> str:
        return self.end


class BatchConfig(BaseModel):
    time_range: Optional[BatchTimeRange] = None
    num_sessions: Optional[int] = None
    app_name: Optional[str] = None

    def validate(self) -> bool:
        # we need for at least one criterion to be set
        if not (
            self.has_time_range() or self.has_num_sessions() or self.has_app_name()
        ):
            return False
        # if no time range but has session ids, then it's valid
        # in this case, assign a default time range
        # as we may iterate over session ids pagination results,
        # date ranges must be fixed
        if not self.has_time_range():
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=7)  # default to 7 days
            start_time_str = start_time.isoformat().replace("+00:00", "Z")
            end_time_str = end_time.isoformat().replace("+00:00", "Z")
            self.time_range = BatchTimeRange(start=start_time_str, end=end_time_str)
        return True

    def has_time_range(self) -> bool:
        return self.time_range is not None

    def get_time_range(self) -> BatchTimeRange:
        return self.time_range

    def has_num_sessions(self) -> bool:
        return self.num_sessions is not None

    def get_num_sessions(self) -> int:
        return self.num_sessions

    def has_app_name(self) -> bool:
        return self.app_name is not None

    def get_app_name(self) -> int:
        return self.app_name


class DataFetchingConfig(BaseModel):
    batch_config: BatchConfig = BatchConfig()
    session_ids: List[str] = []

    def validate(self) -> bool:
        # Batch Request or Session IDs
        _batch_valid = self.batch_config.validate()
        if not _batch_valid and len(self.session_ids) == 0:
            return False
        # If session_ids are provided, batch_config should not be used
        if len(self.session_ids) > 0 and _batch_valid:
            return False
        if len(self.session_ids) == 0 and not _batch_valid:
            return False
        return True

    def is_batch(self) -> bool:
        return len(self.session_ids) == 0

    def get_session_ids(self) -> List[str]:
        return self.session_ids

    def get_batch_config(self) -> BatchConfig:
        return self.batch_config


class MetricOptions(BaseModel):
    """Configuration options for metric computation."""

    computation_level: Optional[List[str]] = None
    write_to_db: Optional[bool] = None
    include_stack_trace: Optional[bool] = False
    include_unmatched_spans: Optional[bool] = False
    reorg_by_entity: Optional[bool] = False

    def get_computation_levels(self) -> List[str]:
        """Get computation levels, defaulting to session if none specified."""
        if self.computation_level is None:
            return ["session"]
        return self.computation_level

    def should_write_to_db(self) -> bool:
        """Check if results should be written to the database."""
        return self.write_to_db if self.write_to_db is not None else False

    def should_include_stack_trace(self) -> bool:
        """Check if stack traces should be included in error messages."""
        return (
            self.include_stack_trace if self.include_stack_trace is not None else False
        )

    def should_include_unmatched_spans(self) -> bool:
        """Check if unmatched spans should be included in the response."""
        return (
            self.include_unmatched_spans
            if self.include_unmatched_spans is not None
            else False
        )

    def should_reorg_by_entity(self) -> bool:
        """Check if results should be reorganized by entity."""
        return self.reorg_by_entity if self.reorg_by_entity is not None else False

    def supports_session(self) -> bool:
        """Check if session-level computation is requested."""
        return "session" in self.get_computation_levels()

    def supports_agent(self) -> bool:
        """Check if agent-level computation is requested."""
        return "agent" in self.get_computation_levels()


class MetricsConfigRequest(BaseModel):
    metrics: List[str] = ["AgentToToolInteractions", "GraphDeterminismScore"]
    llm_judge_config: LLMJudgeConfig = LLMJudgeConfig()
    data_fetching_infos: DataFetchingConfig = DataFetchingConfig()
    metric_options: Optional[MetricOptions] = None

    def validate(self) -> bool:
        if not self.data_fetching_infos.validate():
            return False
        return True

    def is_batch_request(self) -> bool:
        return self.data_fetching_infos.is_batch()

    def get_batch_config(self) -> BatchConfig:
        return self.data_fetching_infos.get_batch_config()

    def get_session_ids(self) -> List[str]:
        return self.data_fetching_infos.get_session_ids()

    def get_metric_options(self) -> MetricOptions:
        """Get metric options, creating default if none provided."""
        if self.metric_options is None:
            return MetricOptions()
        return self.metric_options

    def get_computation_levels(self) -> List[str]:
        """Get computation levels from metric options."""
        return self.get_metric_options().get_computation_levels()

    def should_write_to_db(self) -> bool:
        """Check if results should be written to the database."""
        return self.get_metric_options().should_write_to_db()

    def should_include_stack_trace(self) -> bool:
        """Check if stack traces should be included in error messages."""
        return self.get_metric_options().should_include_stack_trace()

    def should_include_unmatched_spans(self) -> bool:
        """Check if unmatched spans should be included in the response."""
        return self.get_metric_options().should_include_unmatched_spans()

    def should_reorg_by_entity(self) -> bool:
        """Check if results should be reorganized by entity."""
        return self.get_metric_options().should_reorg_by_entity()
