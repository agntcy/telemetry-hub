# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os

import requests
from dotenv import load_dotenv

load_dotenv()

payload = {
    "metrics": [
        "AgentToToolInteractions",
        "deepeval.AnswerRelevancyMetric",
    ],
    "llm_judge_config": {
        "LLM_BASE_MODEL_URL": os.environ["LLM_BASE_MODEL_URL"],
        "LLM_MODEL_NAME": os.environ.get("LLM_MODEL_NAME", ""),
        "LLM_API_KEY": os.environ.get("LLM_API_KEY", ""),
    },
    "data_fetching_infos": {
        "batch_config": {
            "time_range": {
                "start": "2000-06-20T15:04:05Z",
                "end": "2040-06-29T08:52:55Z",
            }
        },
    },
}

response = requests.post("http://127.0.0.1:8000/compute_metrics", json=payload)

print("Status code:", response.status_code)
print("Response:", response.json())
