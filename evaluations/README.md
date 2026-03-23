# Agent Evaluation

MLflow GenAI evaluation framework for the multi-agent loan origination system.

## Quick Start

```bash
# Simple mode (fast, no LLM judge)
MLFLOW_TRACKING_TOKEN=$(oc whoami --show-token) uv run python -m evaluations.run_agent_eval --mode simple

# LLM-as-a-Judge mode (full evaluation)
MLFLOW_TRACKING_TOKEN=$(oc whoami --show-token) uv run python -m evaluations.run_agent_eval --mode llm-judge
```

## Requirements

Configure your `.env` file:

```bash
# Required
MLFLOW_TRACKING_URI=https://your-mlflow-server/mlflow
MLFLOW_EXPERIMENT_NAME=multi-agent-loan-origination

# Required for llm-judge mode
LLM_BASE_URL=https://your-llm-endpoint/v1
LLM_MODEL_CAPABLE=your-model-name
LLM_API_KEY=your-api-key
```

Get an MLflow tracking token (for OpenShift):
```bash
export MLFLOW_TRACKING_TOKEN=$(oc whoami --show-token)
```

## Evaluation Modes

### Simple Mode

Fast, deterministic evaluation without LLM calls.

**Scorers:**
- `contains_expected`: Checks if expected keyword appears in response
- `has_numeric_result`: Checks if response contains numbers
- `response_length`: Ensures adequate response length

```bash
uv run python -m evaluations.run_agent_eval --mode simple
```

### LLM-as-a-Judge Mode

Full evaluation with LLM judges for comprehensive agent assessment.

**Scorers (in addition to simple):**
- `ToolCallCorrectness`: Did the agent call the right tools?
- `ToolCallEfficiency`: Were tool calls minimal and efficient?
- `RelevanceToQuery`: Is the response relevant to the question?
- `Safety`: Is the response safe and appropriate?
- `Guidelines`: Does response follow mortgage assistant guidelines?

```bash
uv run python -m evaluations.run_agent_eval --mode llm-judge
```

## CLI Options

```
usage: run_agent_eval.py [-h] [--agent AGENT] [--mode {simple,llm-judge}]
                         [--judge-model MODEL] [--save-dataset]
                         [--dataset-name NAME] [--verbose]

Options:
  --agent, -a        Agent to evaluate (default: public-assistant)
  --mode, -m         Evaluation mode: simple or llm-judge (default: llm-judge)
  --judge-model, -j  LLM judge model (e.g., openai:/gpt-4.1-mini)
  --save-dataset, -s Save the evaluation dataset to MLflow server
  --dataset-name, -d Name for the MLflow dataset (default: public_assistant_eval)
  --verbose, -v      Enable verbose logging
```

### Examples

```bash
# Simple evaluation
uv run python -m evaluations.run_agent_eval -m simple

# Full evaluation with dataset saved to MLflow
uv run python -m evaluations.run_agent_eval -m llm-judge --save-dataset

# Custom dataset name
uv run python -m evaluations.run_agent_eval --save-dataset --dataset-name my_eval_v2

# Verbose output
uv run python -m evaluations.run_agent_eval -m simple -v
```

## Project Structure

```
evaluations/
├── __init__.py
├── run_agent_eval.py          # Main CLI entry point
├── predictors.py              # Agent predictor wrapper
├── evaluate_agent.ipynb       # Interactive notebook
├── kfp_eval_pipeline.py       # Kubeflow Pipeline definitions
├── pipelines_gen/             # Generated pipeline YAMLs (gitignored)
│   ├── simple_eval_pipeline.yaml
│   └── llm_judge_eval_pipeline.yaml
├── datasets/
│   ├── __init__.py
│   └── public_assistant_simple.py  # Test cases
└── scorers/
    ├── __init__.py
    └── custom_scorers.py      # Custom evaluation scorers
```

## Kubeflow Pipelines

The evaluation can also run as Kubeflow Pipelines on OpenShift AI.

### Pipeline Steps

Both pipelines follow a 4-step structure:

1. **setup_mlflow_op** - Configure MLflow tracking and experiment
2. **create_dataset_op** - Create/load evaluation dataset in MLflow
3. **run_eval_op** - Run evaluation (simple or LLM-judge)
4. **report_results_op** - Generate and display evaluation report

### Pipeline Parameters

**Simple Pipeline:**
| Parameter | Description | Default |
|-----------|-------------|---------|
| `mlflow_tracking_uri` | MLflow server URL | (required) |
| `mlflow_experiment_name` | Experiment name | `multi-agent-loan-origination` |
| `agent_name` | Agent to evaluate | `public-assistant` |
| `dataset_name` | MLflow dataset name | `public_assistant_eval` |
| `mlflow_secret_name` | K8s secret for MLflow token | `mlflow-credentials` |

**LLM-Judge Pipeline (additional):**
| Parameter | Description | Default |
|-----------|-------------|---------|
| `llm_base_url` | LLM endpoint URL | (required) |
| `llm_model` | Model for LLM judge | `qwen3-14b` |
| `llm_secret_name` | K8s secret for LLM API key | `llm-credentials` |

### Required Kubernetes Secrets

```yaml
# mlflow-credentials
apiVersion: v1
kind: Secret
metadata:
  name: mlflow-credentials
stringData:
  MLFLOW_TRACKING_TOKEN: <your-token>

# llm-credentials (for LLM-judge mode)
apiVersion: v1
kind: Secret
metadata:
  name: llm-credentials
stringData:
  LLM_API_KEY: <your-api-key>
```

## Dataset Format

Test cases follow MLflow's expected format:

```python
{
    "inputs": {"user_message": "What loan products do you offer?"},
    "expectations": {
        "expected_answer": "30-year",  # Keyword in response
        "expected_tool_calls": [{"name": "product_info"}],  # Tools to call
        "expected_topics": ["fixed", "FHA", "VA"],  # Topics to cover
        "forbidden_content": [],  # Content to avoid
    },
}
```

## Viewing Results

After running an evaluation:

1. Open your MLflow tracking URI in a browser
2. Go to **Experiments** > `your-experiment-eval`
3. Click on **Evaluation Runs** tab
4. Select your run to view per-trace assessments
5. Enable **All Assessments** in the Columns dropdown to see LLM judge scores