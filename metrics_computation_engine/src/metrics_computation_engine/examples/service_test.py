# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import pprint

import requests
from dotenv import load_dotenv

load_dotenv()

payload = {
    "metrics": [
        "ToolUtilizationAccuracy",
        "ToolErrorRate",
        "ToolError",
        "AgentToToolInteractions",
        "AgentToAgentInteractions",
        "Groundedness",
        "CyclesCount",
    ],
    "llm_judge_config": {
        "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
        "LLM_MODEL_NAME": os.environ["LLM_MODEL_NAME"],
        "LLM_BASE_MODEL_URL": os.environ.get("LLM_BASE_MODEL_URL", ""),
        "CUSTOM_API_KEY": os.environ.get("CUSTOM_API_KEY", ""),
    },
    "batch_config": {
        "time_range": {"start": "2000-06-20T15:04:05Z", "end": "2040-06-29T08:52:55Z"}
    },
}

response = requests.post("http://127.0.0.1:8000/compute_metrics", json=payload)

print("Status code:", response.status_code)
pprint.pprint(response.json(), indent=2)
