# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from metrics_computation_engine.llm_judge.llm import LLMClient
from metrics_computation_engine.llm_judge.prompts import judge_system_prompt
from metrics_computation_engine.llm_judge.utils.response_parsing import (
    parse_key_from_nested_dict,
    safe_json_from_llm,
)


class Jury:
    def __init__(self, llm_configs, num_models=1):
        self.llms = [LLMClient(llm_configs) for _ in range(num_models)]
        self.system_message = {"role": "system", "content": judge_system_prompt}

    def augment_prompt_with_schema(self, prompt: str, response_format: Any = None):
        # Takes a Pydantic model representation of the response format for structured outputs and constructs the instruction to return accordingly.
        json_prompt = "\n".join(
            [
                f"`{k}`: {v['description']}"
                for k, v in response_format.model_json_schema()["properties"].items()
            ]
        )
        judge_prompt = (
            prompt
            + f"\n Please provide your response in the following json schema\n {json_prompt}"
        )

        return judge_prompt

    def consensus_score(self, judge_responses):
        total_score = 0
        for res in judge_responses:
            content = res.choices[-1].message.content
            res_dict = safe_json_from_llm(content)

            if not res_dict:
                raise ValueError("Unable to parse LLM response to dict.")

            total_score += parse_key_from_nested_dict(res_dict, "metric_score")

        cons_score = total_score / len(judge_responses)

        # TODO: Put reasoning consolidation here.
        feedback = parse_key_from_nested_dict(res_dict, "score_reasoning")

        return {"metric_score": cons_score, "score_reasoning": feedback}

    def judge(self, prompt: str, response_format: Any = None, mode="default"):
        query_params = {"response_format": {"type": "json_object"}}
        judge_prompt = self.augment_prompt_with_schema(prompt, response_format)

        messages = [self.system_message, {"role": "user", "content": judge_prompt}]

        results = []
        for llm in self.llms:
            res = llm.query(messages, **query_params)
            results.append(res)

        consensus = self.consensus_score(results)
        score, reasoning = consensus["metric_score"], consensus["score_reasoning"]
        return score, reasoning
