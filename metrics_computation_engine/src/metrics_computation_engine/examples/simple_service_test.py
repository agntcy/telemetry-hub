# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Simple service test for manual execution.

This is a simplified version of the service test that can be run
when the server is already running manually.
"""

import os

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_simple_service():
    """Simple test to verify the service is working."""
    BASE_URL = "http://127.0.0.1:8000"

    payload = {
        "metrics": ["AgentToToolInteractions"],
        "llm_judge_config": {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
            "CUSTOM_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
            "LLM_MODEL_NAME": os.environ.get("LLM_MODEL_NAME", ""),
        },
    }

    try:
        response = requests.post(f"{BASE_URL}/compute_metrics", json=payload)
        print(f"✅ Status code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Response contains 'metrics': {'metrics' in data}")
            print(f"✅ Response contains 'results': {'results' in data}")
            if "metrics" in data:
                print(f"📊 Available metrics: {data['metrics']}")
        else:
            print(f"❌ Error response: {response.text}")

    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Is the server running?")
        print("💡 Start the server with: mce-server")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    print("🧪 Testing Metrics Computation Service...")
    print("📋 Make sure the server is running: mce-server")
    print()
    test_simple_service()
