# 🧠 3rd Party Metrics Integration Test

This demonstrates the integration of a 3rd party metric (DeepEval's AnswerRelevancyMetric) into the MCE. Where MCEmetrics are run alongside the 3rd party metrics.

- [DeepEval](https://github.com/confident-ai/deepeval)

---

## 📦 Installation

Make sure you have Python 3.8+ installed. Then:

```bash
pip install -r requirements.txt.txt
```

> **Note:** Some examples may require additional dependencies — check the import statements in each script.

---

## 🔧 Environment Variables

Set the following environment variables before running the tests:

```bash
export OPENAI_API_KEY=<your_openai_api_key>
```

---

### 🚀 How to Run

After installing the dependencies and setting environment variables, run an example with:

```bash
python third_party_plugins_test.py
```

You should get an expected output of
```bash
['AgentToAgentInteractions', 'Answer Relevancy']
{'AgentToAgentInteractions': MetricResult(metric_name='AgentToAgentInteractions',
                                          value=[('supervisor -> research', 1), ('research -> supervisor', 1)],
                                          metadata={'metric_type': 'counter'},
                                          success='success',
                                          error_message=None),
 'Answer Relevancy': MetricResult(metric_name='Answer Relevancy',
                                  value=1.0,
                                  metadata={'threshold': 0.5, 'success': True, 'reason': 'The score is 1.00 because the response accurately and directly answered the question without any irrelevant information.', 'evaluation_cost': 0.0146, 'verbose_logs': 'Statements:\n[\n    "The 31st President of the United States was Herbert Hoover.",\n    "He served from 1929 to 1933.",\n    "You can find more information about him on Wikipedia."\n] \n \nVerdicts:\n[\n    {\n        "verdict": "yes",\n        "reason": null\n    },\n    {\n        "verdict": "yes",\n        "reason": null\n    },\n    {\n        "verdict": "idk",\n        "reason": null\n    }\n]'},
                                  success=True,
                                  error_message=None)}
```
---
