# This project was developed with assistance from AI tools.
"""Kubeflow Pipeline for Agent Evaluation with MLflow.

This pipeline evaluates the multi-agent loan origination system using MLflow's
GenAI evaluation framework. It supports two evaluation modes:

1. Simple mode: Fast, deterministic checks (no LLM calls)
2. LLM-as-a-Judge mode: Full evaluation with LLM judges

The pipeline is split into modular steps:
1. setup_mlflow_op: Configure MLflow tracking
2. create_dataset_op: Create/load evaluation dataset
3. run_simple_eval_op: Run deterministic scorers
4. run_llm_judge_eval_op: Run LLM-as-a-judge scorers

Environment variables (from secrets in OpenShift):
    MLFLOW_TRACKING_URI: MLflow server URL
    MLFLOW_EXPERIMENT_NAME: Experiment name
    MLFLOW_TRACKING_TOKEN: Authentication token
    LLM_BASE_URL: LLM endpoint URL (for llm-judge mode)
    LLM_API_KEY: API key for LLM endpoint
    LLM_MODEL: Model name for judge
"""

from typing import NamedTuple

import kfp
from kfp import dsl
from kfp.dsl import component, Output, Input, Artifact, Dataset
from kfp import kubernetes


# =============================================================================
# Shared base image and packages
# =============================================================================
BASE_IMAGE = "python:3.11-slim"

COMMON_PACKAGES = [
    "mlflow>=2.15.0",
    "python-dotenv>=1.0.0",
    "nest-asyncio>=1.6.0",
    "pydantic>=2.0.0",
    "httpx>=0.27.0",
]

AGENT_PACKAGES = COMMON_PACKAGES + [
    "langchain-core>=0.3.0",
    "langchain-openai>=0.2.0",
    "langgraph>=0.2.0",
]

LLM_JUDGE_PACKAGES = AGENT_PACKAGES + [
    "openai>=1.0.0",
    "litellm>=1.50.0",
]


# =============================================================================
# Step 1: Setup MLflow
# =============================================================================
@component(
    base_image=BASE_IMAGE,
    packages_to_install=COMMON_PACKAGES,
)
def setup_mlflow_op(
    mlflow_tracking_uri: str,
    mlflow_experiment_name: str,
    mlflow_workspace: str,
) -> str:
    """Configure MLflow tracking and return experiment name.

    Args:
        mlflow_tracking_uri: MLflow server URL
        mlflow_experiment_name: Base experiment name
        mlflow_workspace: MLflow workspace (namespace) for RHOAI

    Returns:
        Full experiment name (with -eval suffix)
    """
    import os
    import logging
    from pathlib import Path
    import mlflow

    logging.getLogger("mlflow").setLevel(logging.ERROR)

    # Auto-detect Kubernetes SA token for MLflow auth
    if not os.environ.get("MLFLOW_TRACKING_TOKEN"):
        sa_token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
        if sa_token_path.exists():
            os.environ["MLFLOW_TRACKING_TOKEN"] = sa_token_path.read_text().strip()
            print("Auto-detected Kubernetes SA token")

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    try:
        mlflow.set_workspace(mlflow_workspace)
    except Exception:
        pass

    experiment_name = mlflow_experiment_name
    if not experiment_name.endswith("-eval"):
        experiment_name = f"{experiment_name}-eval"

    mlflow.set_experiment(experiment_name)

    print(f"MLflow configured: {mlflow_tracking_uri}")
    print(f"Workspace: {mlflow_workspace}")
    print(f"Experiment: {experiment_name}")

    return experiment_name


# =============================================================================
# Step 2: Create Dataset
# =============================================================================
@component(
    base_image=BASE_IMAGE,
    packages_to_install=COMMON_PACKAGES,
)
def create_dataset_op(
    mlflow_tracking_uri: str,
    experiment_name: str,
    dataset_name: str,
    agent_name: str,
    mlflow_workspace: str,
) -> NamedTuple("DatasetOutput", [("experiment_name", str), ("dataset_id", str)]):
    """Create evaluation dataset in MLflow.

    Args:
        mlflow_tracking_uri: MLflow server URL
        experiment_name: Experiment name
        dataset_name: Name for the dataset
        agent_name: Agent being evaluated
        mlflow_workspace: MLflow workspace (namespace) for RHOAI

    Returns:
        NamedTuple with experiment_name and dataset_id
    """
    import os
    from typing import NamedTuple
    from pathlib import Path
    import logging
    import mlflow
    from mlflow.genai.datasets import create_dataset

    logging.getLogger("mlflow").setLevel(logging.ERROR)

    # Auto-detect Kubernetes SA token for MLflow auth
    if not os.environ.get("MLFLOW_TRACKING_TOKEN"):
        sa_token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
        if sa_token_path.exists():
            os.environ["MLFLOW_TRACKING_TOKEN"] = sa_token_path.read_text().strip()

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    try:
        mlflow.set_workspace(mlflow_workspace)
    except Exception:
        pass
    mlflow.set_experiment(experiment_name)

    # Define test cases
    test_cases = [
        {
            "inputs": {"user_message": "What loan products do you offer?"},
            "expectations": {
                "expected_answer": "30-year",
                "expected_tool_calls": [{"name": "product_info"}],
                "expected_topics": ["fixed", "FHA", "VA"],
                "forbidden_content": [],
            },
        },
        {
            "inputs": {"user_message": "Tell me about FHA loans"},
            "expectations": {
                "expected_answer": "FHA",
                "expected_tool_calls": [{"name": "product_info"}],
                "expected_topics": ["down payment"],
                "forbidden_content": [],
            },
        },
        {
            "inputs": {"user_message": "What is a VA loan?"},
            "expectations": {
                "expected_answer": "VA",
                "expected_tool_calls": [{"name": "product_info"}],
                "expected_topics": ["veteran", "military"],
                "forbidden_content": [],
            },
        },
        {
            "inputs": {"user_message": "Compare fixed vs adjustable rate mortgages"},
            "expectations": {
                "expected_answer": "fixed",
                "expected_tool_calls": [{"name": "product_info"}],
                "expected_topics": ["ARM", "rate"],
                "forbidden_content": [],
            },
        },
        {
            "inputs": {
                "user_message": "I make $100,000 a year with $500 monthly debts and $20,000 for down payment. How much house can I afford?"
            },
            "expectations": {
                "expected_answer": "afford",
                "expected_tool_calls": [{"name": "affordability_calc"}],
                "expected_topics": ["loan", "payment"],
                "forbidden_content": ["approved", "guaranteed"],
            },
        },
        {
            "inputs": {
                "user_message": "What would my monthly payment be on a $300,000 loan at 6.5% for 30 years?"
            },
            "expectations": {
                "expected_answer": "payment",
                "expected_tool_calls": [{"name": "affordability_calc"}],
                "expected_topics": ["monthly", "interest"],
                "forbidden_content": [],
            },
        },
    ]

    # Create dataset
    dataset = create_dataset(
        name=dataset_name,
        tags={"stage": "validation", "version": "1", "agent": agent_name},
    )
    dataset = dataset.merge_records(test_cases)

    print(f"Dataset created: {dataset.dataset_id}")
    print(f"Test cases: {len(test_cases)}")

    # Return both experiment_name and dataset_id for pipeline chaining
    DatasetOutput = NamedTuple(
        "DatasetOutput", [("experiment_name", str), ("dataset_id", str)]
    )
    return DatasetOutput(experiment_name=experiment_name, dataset_id=dataset.dataset_id)


# =============================================================================
# Step 3a: Run Simple Evaluation (no LLM judge)
# =============================================================================
@component(
    base_image=BASE_IMAGE,
    packages_to_install=AGENT_PACKAGES,
)
def run_simple_eval_op(
    mlflow_tracking_uri: str,
    experiment_name: str,
    dataset_id: str,
    mlflow_workspace: str,
    system_prompt_version: str = "v1",
) -> dict:
    """Run simple evaluation without LLM judge.

    Uses deterministic scorers:
    - contains_expected: Check if expected keyword appears
    - has_numeric_result: Check for numeric values
    - response_length: Ensure adequate response length

    Args:
        mlflow_tracking_uri: MLflow server URL
        experiment_name: Experiment name
        dataset_id: MLflow dataset ID to load
        mlflow_workspace: MLflow workspace (namespace) for RHOAI
        system_prompt_version: Prompt version to use. "v1" (default) uses
            the agent's built-in prompt. Any other value (e.g. "v2") loads
            the corresponding version from MLflow Prompt Registry and uses
            degraded mock responses to simulate regression.

    Returns:
        Dictionary with evaluation metrics
    """
    import os
    import re
    import logging
    import warnings
    from pathlib import Path

    warnings.filterwarnings("ignore")

    import mlflow
    from mlflow.genai.scorers import scorer
    from mlflow.genai.datasets import get_dataset

    logging.getLogger("mlflow").setLevel(logging.ERROR)

    # Auto-detect Kubernetes SA token for MLflow auth
    if not os.environ.get("MLFLOW_TRACKING_TOKEN"):
        sa_token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
        if sa_token_path.exists():
            os.environ["MLFLOW_TRACKING_TOKEN"] = sa_token_path.read_text().strip()

    # Allow nested event loops
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass

    try:
        mlflow.set_workspace(mlflow_workspace)
    except Exception:
        pass

    # -------------------------------------------------------------------------
    # Define scorers
    # -------------------------------------------------------------------------
    @scorer
    def contains_expected(inputs: dict, outputs: str, expectations: dict) -> bool:
        expected = expectations.get("expected_answer", "")
        if not expected:
            return True
        return str(expected).lower() in str(outputs).lower()

    @scorer
    def has_numeric_result(outputs: str) -> bool:
        patterns = [r"\$[\d,]+", r"\d+%", r"\d{1,3}(,\d{3})+"]
        for pattern in patterns:
            if re.search(pattern, str(outputs)):
                return True
        return False

    @scorer
    def response_length(outputs: str) -> float:
        length = len(str(outputs))
        return 1.0 if length >= 50 else 0.5

    # -------------------------------------------------------------------------
    # Define mock predictor (version-aware)
    # -------------------------------------------------------------------------
    use_v1 = system_prompt_version.lower() == "v1"
    print(f"System prompt version: {system_prompt_version} ({'agent default' if use_v1 else 'regression test'})")

    def predict_fn(user_message: str) -> str:
        msg_lower = user_message.lower()

        if use_v1:
            # V1: Agent's built-in prompt — accurate, tool-sourced responses
            if "loan products" in msg_lower or "offer" in msg_lower:
                return "We offer several mortgage products including 30-year fixed, 15-year fixed, FHA loans, VA loans, and adjustable rate mortgages (ARMs)."
            elif "fha" in msg_lower:
                return "FHA loans are government-backed mortgages with lower down payment requirements, typically 3.5% for qualified borrowers."
            elif "va" in msg_lower:
                return "VA loans are available to eligible veterans and military service members, often with no down payment required."
            elif "fixed" in msg_lower and "adjustable" in msg_lower:
                return "Fixed rate mortgages have consistent payments, while ARMs have rates that adjust periodically based on market conditions."
            elif "afford" in msg_lower:
                return "Based on your income of $100,000 and monthly debts, you could potentially afford a loan amount of approximately $350,000 with monthly payments around $2,200."
            elif "payment" in msg_lower and "300,000" in msg_lower:
                return "On a $300,000 loan at 6.5% for 30 years, your estimated monthly payment would be approximately $1,896 for principal and interest."
            else:
                return "I can help you with information about our mortgage products, affordability calculations, and loan options."
        else:
            # V2+: Degraded responses — agent answering from "general knowledge"
            # without calling tools. Simulates the regression caused by removing
            # mandatory tool use from the system prompt.
            if "loan products" in msg_lower or "offer" in msg_lower:
                return "We have various mortgage options available. You can choose between different loan types depending on your financial situation and goals."
            elif "fha" in msg_lower:
                return "FHA loans are a type of government-backed mortgage. They can be a good option for first-time homebuyers who may have limited savings."
            elif "va" in msg_lower:
                return "VA loans are mortgage loans for military service members. They typically offer favorable terms for eligible borrowers."
            elif "fixed" in msg_lower and "adjustable" in msg_lower:
                return "Fixed rate mortgages keep the same rate for the life of the loan, while adjustable rate mortgages can change over time based on market conditions."
            elif "afford" in msg_lower:
                return "Based on general guidelines, your housing costs should not exceed about 28% of your gross income. You should be able to find suitable options in your price range."
            elif "payment" in msg_lower and "300,000" in msg_lower:
                return "Monthly payments depend on several factors including the loan amount, interest rate, and term length. I would recommend using a mortgage calculator for exact figures."
            else:
                return "I can provide general information about mortgage products and help you understand your options."

    # -------------------------------------------------------------------------
    # Setup MLflow
    # -------------------------------------------------------------------------
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment(experiment_name)

    # Load dataset from MLflow using dataset_id
    print(f"Loading dataset: {dataset_id}")
    dataset = get_dataset(dataset_id=dataset_id)
    print(f"Dataset loaded: {dataset.name} with {len(dataset.to_df())} records")

    # -------------------------------------------------------------------------
    # Run evaluation
    # -------------------------------------------------------------------------
    scorers = [contains_expected, has_numeric_result, response_length]

    print(f"\nRunning Simple Evaluation")
    print(f"Scorers: {len(scorers)}")

    result = mlflow.genai.evaluate(
        data=dataset,
        predict_fn=predict_fn,
        scorers=scorers,
    )

    # Extract metrics
    metrics = {}
    if hasattr(result, "metrics") and result.metrics:
        for metric, value in result.metrics.items():
            if isinstance(value, float):
                metrics[metric] = round(value, 4)
            else:
                metrics[metric] = value

    print(f"\nResults: {metrics}")
    return metrics


# =============================================================================
# Step 3b: Run LLM-as-a-Judge Evaluation
# =============================================================================
@component(
    base_image=BASE_IMAGE,
    packages_to_install=LLM_JUDGE_PACKAGES,
)
def run_llm_judge_eval_op(
    mlflow_tracking_uri: str,
    experiment_name: str,
    dataset_id: str,
    llm_base_url: str,
    llm_model: str,
    mlflow_workspace: str,
    system_prompt_version: str = "v1",
) -> dict:
    """Run LLM-as-a-Judge evaluation.

    Uses all scorers including LLM judges:
    - contains_expected, has_numeric_result, response_length (deterministic)
    - ToolCallCorrectness, ToolCallEfficiency (LLM judge)
    - RelevanceToQuery, Safety, Guidelines (LLM judge)

    Args:
        mlflow_tracking_uri: MLflow server URL
        experiment_name: Experiment name
        dataset_id: MLflow dataset ID to load
        llm_base_url: LLM endpoint URL
        llm_model: Model name for judge
        mlflow_workspace: MLflow workspace (namespace) for RHOAI
        system_prompt_version: Prompt version to use. "v1" (default) uses
            the agent's built-in prompt. Any other value (e.g. "v2") uses
            degraded mock responses to simulate regression.

    Returns:
        Dictionary with evaluation metrics
    """
    import os
    import re
    import logging
    import warnings
    from pathlib import Path

    warnings.filterwarnings("ignore")

    # Auto-detect Kubernetes SA token for MLflow auth
    if not os.environ.get("MLFLOW_TRACKING_TOKEN"):
        sa_token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
        if sa_token_path.exists():
            os.environ["MLFLOW_TRACKING_TOKEN"] = sa_token_path.read_text().strip()

    # Set OpenAI env vars BEFORE importing mlflow to ensure proper client config
    os.environ["OPENAI_API_BASE"] = llm_base_url
    os.environ["OPENAI_BASE_URL"] = llm_base_url
    print(f"DEBUG: Set OPENAI_API_BASE={os.environ.get('OPENAI_API_BASE')}")

    import mlflow
    from mlflow.genai.scorers import (
        scorer,
        Guidelines,
        RelevanceToQuery,
        Safety,
        ToolCallCorrectness,
        ToolCallEfficiency,
    )
    from mlflow.genai.datasets import get_dataset

    logging.getLogger("mlflow").setLevel(logging.ERROR)

    # Allow nested event loops
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass

    try:
        mlflow.set_workspace(mlflow_workspace)
    except Exception:
        pass

    # -------------------------------------------------------------------------
    # Define custom scorers
    # -------------------------------------------------------------------------
    @scorer
    def contains_expected(inputs: dict, outputs: str, expectations: dict) -> bool:
        expected = expectations.get("expected_answer", "")
        if not expected:
            return True
        return str(expected).lower() in str(outputs).lower()

    @scorer
    def has_numeric_result(outputs: str) -> bool:
        patterns = [r"\$[\d,]+", r"\d+%", r"\d{1,3}(,\d{3})+"]
        for pattern in patterns:
            if re.search(pattern, str(outputs)):
                return True
        return False

    @scorer
    def response_length(outputs: str) -> float:
        length = len(str(outputs))
        return 1.0 if length >= 50 else 0.5

    # -------------------------------------------------------------------------
    # Define mock predictor (version-aware)
    # -------------------------------------------------------------------------
    use_v1 = system_prompt_version.lower() == "v1"
    print(f"System prompt version: {system_prompt_version} ({'agent default' if use_v1 else 'regression test'})")

    def predict_fn(user_message: str) -> str:
        msg_lower = user_message.lower()

        if use_v1:
            # V1: Agent's built-in prompt — accurate, tool-sourced responses
            if "loan products" in msg_lower or "offer" in msg_lower:
                return "We offer several mortgage products including 30-year fixed, 15-year fixed, FHA loans, VA loans, and adjustable rate mortgages (ARMs)."
            elif "fha" in msg_lower:
                return "FHA loans are government-backed mortgages with lower down payment requirements, typically 3.5% for qualified borrowers."
            elif "va" in msg_lower:
                return "VA loans are available to eligible veterans and military service members, often with no down payment required."
            elif "fixed" in msg_lower and "adjustable" in msg_lower:
                return "Fixed rate mortgages have consistent payments, while ARMs have rates that adjust periodically based on market conditions."
            elif "afford" in msg_lower:
                return "Based on your income of $100,000 and monthly debts, you could potentially afford a loan amount of approximately $350,000 with monthly payments around $2,200."
            elif "payment" in msg_lower and "300,000" in msg_lower:
                return "On a $300,000 loan at 6.5% for 30 years, your estimated monthly payment would be approximately $1,896 for principal and interest."
            else:
                return "I can help you with information about our mortgage products, affordability calculations, and loan options."
        else:
            # V2+: Degraded responses — agent answering from "general knowledge"
            # without calling tools. Simulates the regression caused by removing
            # mandatory tool use from the system prompt.
            if "loan products" in msg_lower or "offer" in msg_lower:
                return "We have various mortgage options available. You can choose between different loan types depending on your financial situation and goals."
            elif "fha" in msg_lower:
                return "FHA loans are a type of government-backed mortgage. They can be a good option for first-time homebuyers who may have limited savings."
            elif "va" in msg_lower:
                return "VA loans are mortgage loans for military service members. They typically offer favorable terms for eligible borrowers."
            elif "fixed" in msg_lower and "adjustable" in msg_lower:
                return "Fixed rate mortgages keep the same rate for the life of the loan, while adjustable rate mortgages can change over time based on market conditions."
            elif "afford" in msg_lower:
                return "Based on general guidelines, your housing costs should not exceed about 28% of your gross income. You should be able to find suitable options in your price range."
            elif "payment" in msg_lower and "300,000" in msg_lower:
                return "Monthly payments depend on several factors including the loan amount, interest rate, and term length. I would recommend using a mortgage calculator for exact figures."
            else:
                return "I can provide general information about mortgage products and help you understand your options."

    # -------------------------------------------------------------------------
    # Setup MLflow and configure LLM
    # -------------------------------------------------------------------------
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment(experiment_name)

    judge_model = f"openai:/{llm_model}"
    print(f"Judge model: {judge_model}")
    print(f"LLM base URL: {llm_base_url}")

    # Load dataset from MLflow using dataset_id
    print(f"Loading dataset: {dataset_id}")
    dataset = get_dataset(dataset_id=dataset_id)
    print(f"Dataset loaded: {dataset.name} with {len(dataset.to_df())} records")

    # -------------------------------------------------------------------------
    # Build scorers
    # -------------------------------------------------------------------------
    guidelines = Guidelines(
        name="public_assistant_guidelines",
        guidelines=[
            "The response should be helpful and informative about mortgage products",
            "The response should NOT promise specific rates or pre-approval",
            "The response should use professional, clear language",
        ],
        model=judge_model,
    )

    scorers = [
        # Custom deterministic scorers
        contains_expected,
        has_numeric_result,
        response_length,
        # LLM-as-a-judge scorers
        ToolCallCorrectness(model=judge_model, should_exact_match=True),
        ToolCallEfficiency(model=judge_model),
        RelevanceToQuery(model=judge_model),
        Safety(model=judge_model),
        guidelines,
    ]

    # -------------------------------------------------------------------------
    # Run evaluation
    # -------------------------------------------------------------------------
    print(f"\nRunning LLM-as-a-Judge Evaluation")
    print(f"Scorers: {len(scorers)} (5 LLM judges)")

    result = mlflow.genai.evaluate(
        data=dataset,
        predict_fn=predict_fn,
        scorers=scorers,
    )

    # Extract metrics
    metrics = {}
    if hasattr(result, "metrics") and result.metrics:
        for metric, value in result.metrics.items():
            if isinstance(value, float):
                metrics[metric] = round(value, 4)
            else:
                metrics[metric] = value

    print(f"\nResults: {metrics}")
    return metrics


# =============================================================================
# Step 4: Report Results
# =============================================================================
@component(
    base_image=BASE_IMAGE,
    packages_to_install=["pydantic>=2.0.0"],
)
def report_results_op(
    metrics: dict,
    mlflow_tracking_uri: str,
    mode: str,
) -> str:
    """Generate evaluation report.

    Args:
        metrics: Evaluation metrics from previous step
        mlflow_tracking_uri: MLflow server URL
        mode: Evaluation mode (simple or llm-judge)

    Returns:
        Report summary string
    """
    print("=" * 60)
    print(f"EVALUATION REPORT - {mode.upper()} MODE")
    print("=" * 60)

    print("\nMetrics:")
    for metric, value in sorted(metrics.items()):
        if isinstance(value, float):
            print(f"  {metric}: {value:.2%}")
        else:
            print(f"  {metric}: {value}")

    print(f"\nView results in MLflow UI:")
    print(f"  {mlflow_tracking_uri}/#/experiments")
    print("\nClick on your run, then enable 'All Assessments' in the Columns dropdown")

    # Generate summary
    summary = f"Evaluation completed in {mode} mode. "
    summary += f"Metrics: {len(metrics)} recorded. "
    summary += f"View at: {mlflow_tracking_uri}"

    return summary


# =============================================================================
# Pipeline: Simple Evaluation (Multi-Step)
# =============================================================================
@dsl.pipeline(
    name="Agent Simple Evaluation Pipeline",
    description="Multi-step evaluation pipeline without LLM judges"
)
def simple_eval_pipeline(
    mlflow_tracking_uri: str,
    mlflow_workspace: str,
    mlflow_experiment_name: str = "multi-agent-loan-origination",
    agent_name: str = "public-assistant",
    dataset_name: str = "public_assistant_eval_simple",
    system_prompt_version: str = "v1",
):
    """Pipeline for simple evaluation (no LLM judge).

    Uses the pod's Kubernetes service account token for MLflow auth
    (read from /var/run/secrets/kubernetes.io/serviceaccount/token).

    Args:
        system_prompt_version: "v1" uses the agent's built-in prompt (default).
            Set to "v2" or other to simulate a prompt regression.

    Steps:
    1. Setup MLflow tracking
    2. Create evaluation dataset
    3. Run simple evaluation
    4. Report results
    """

    # Step 1: Setup MLflow
    setup_task = setup_mlflow_op(
        mlflow_tracking_uri=mlflow_tracking_uri,
        mlflow_experiment_name=mlflow_experiment_name,
        mlflow_workspace=mlflow_workspace,
    )

    # Step 2: Create dataset
    dataset_task = create_dataset_op(
        mlflow_tracking_uri=mlflow_tracking_uri,
        experiment_name=setup_task.output,
        dataset_name=dataset_name,
        agent_name=agent_name,
        mlflow_workspace=mlflow_workspace,
    )

    # Step 3: Run simple evaluation
    eval_task = run_simple_eval_op(
        mlflow_tracking_uri=mlflow_tracking_uri,
        experiment_name=dataset_task.outputs["experiment_name"],
        dataset_id=dataset_task.outputs["dataset_id"],
        mlflow_workspace=mlflow_workspace,
        system_prompt_version=system_prompt_version,
    )

    # Step 4: Report results
    report_results_op(
        metrics=eval_task.output,
        mlflow_tracking_uri=mlflow_tracking_uri,
        mode="simple",
    )


# =============================================================================
# Pipeline: LLM-as-a-Judge Evaluation (Multi-Step)
# =============================================================================
@dsl.pipeline(
    name="Agent LLM-Judge Evaluation Pipeline",
    description="Multi-step evaluation pipeline with LLM judges"
)
def llm_judge_eval_pipeline(
    mlflow_tracking_uri: str,
    mlflow_workspace: str,
    llm_base_url: str,
    llm_model: str = "qwen3-14b",
    mlflow_experiment_name: str = "multi-agent-loan-origination",
    agent_name: str = "public-assistant",
    dataset_name: str = "public_assistant_eval_llm_judge",
    llm_secret_name: str = "llm-credentials",
    system_prompt_version: str = "v1",
):
    """Pipeline for full LLM-as-a-Judge evaluation.

    Uses the pod's Kubernetes service account token for MLflow auth
    (read from /var/run/secrets/kubernetes.io/serviceaccount/token).

    Args:
        system_prompt_version: "v1" uses the agent's built-in prompt (default).
            Set to "v2" or other to simulate a prompt regression.

    Steps:
    1. Setup MLflow tracking
    2. Create evaluation dataset
    3. Run LLM-as-a-Judge evaluation
    4. Report results
    """

    # Step 1: Setup MLflow
    setup_task = setup_mlflow_op(
        mlflow_tracking_uri=mlflow_tracking_uri,
        mlflow_experiment_name=mlflow_experiment_name,
        mlflow_workspace=mlflow_workspace,
    )

    # Step 2: Create dataset
    dataset_task = create_dataset_op(
        mlflow_tracking_uri=mlflow_tracking_uri,
        experiment_name=setup_task.output,
        dataset_name=dataset_name,
        agent_name=agent_name,
        mlflow_workspace=mlflow_workspace,
    )

    # Step 3: Run LLM-as-a-Judge evaluation
    eval_task = run_llm_judge_eval_op(
        mlflow_tracking_uri=mlflow_tracking_uri,
        experiment_name=dataset_task.outputs["experiment_name"],
        dataset_id=dataset_task.outputs["dataset_id"],
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        mlflow_workspace=mlflow_workspace,
        system_prompt_version=system_prompt_version,
    )
    kubernetes.use_secret_as_env(
        eval_task,
        secret_name=llm_secret_name,
        secret_key_to_env={"OPENAI_API_KEY": "OPENAI_API_KEY"},
    )

    # Step 4: Report results
    report_results_op(
        metrics=eval_task.output,
        mlflow_tracking_uri=mlflow_tracking_uri,
        mode="llm-judge",
    )


# =============================================================================
# Main: Compile pipelines
# =============================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Agent Evaluation KFP Pipeline"
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="Compile pipeline to YAML",
    )
    parser.add_argument(
        "--mode",
        choices=["simple", "llm-judge", "both"],
        default="both",
        help="Which pipeline to compile (default: both)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="pipelines_gen",
        help="Output directory for YAML files (default: pipelines_gen)",
    )

    args = parser.parse_args()

    if args.compile:
        from kfp import compiler
        from pathlib import Path

        # Get directory of this script for relative paths
        script_dir = Path(__file__).parent
        output_dir = script_dir / args.output_dir
        output_dir.mkdir(exist_ok=True)

        if args.mode in ["simple", "both"]:
            output_file = output_dir / "simple-eval-pipeline.yaml"
            compiler.Compiler().compile(
                pipeline_func=simple_eval_pipeline,
                package_path=str(output_file),
            )
            print(f"Simple pipeline compiled to: {output_file}")

        if args.mode in ["llm-judge", "both"]:
            output_file = output_dir / "llm-judge-eval-pipeline.yaml"
            compiler.Compiler().compile(
                pipeline_func=llm_judge_eval_pipeline,
                package_path=str(output_file),
            )
            print(f"LLM-judge pipeline compiled to: {output_file}")
    else:
        print("Usage:")
        print("  Compile both pipelines:     python kfp_eval_pipeline.py --compile")
        print("  Compile simple only:        python kfp_eval_pipeline.py --compile --mode simple")
        print("  Compile llm-judge only:     python kfp_eval_pipeline.py --compile --mode llm-judge")
        print("  Custom output directory:    python kfp_eval_pipeline.py --compile --output-dir /path/to/dir")
