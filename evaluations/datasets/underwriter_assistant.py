# This project was developed with assistance from AI tools.
"""Evaluation dataset for Underwriter Assistant.

The underwriter assistant helps with:
- Risk assessment (DTI, LTV, credit analysis)
- Compliance checking (TRID, ECOA, fair lending)
- Condition management (add, clear, track)
- Decision documentation (approve, deny, suspend)
- Document verification
- Fraud detection alerts
"""

UNDERWRITER_ASSISTANT_DATASET = [
    # Risk Assessment
    {
        "inputs": {"user_message": "What's the DTI ratio for application 667?"},
        "expectations": {
            "expected_answer": "DTI",
            "expected_tools": ["uw_risk_assessment"],
            "expected_topics": ["DTI", "ratio", "income", "debt"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "risk_assessment",
            "complexity": "simple",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "Analyze the credit profile for application 667"},
        "expectations": {
            "expected_answer": "credit",
            "expected_tools": ["uw_risk_assessment"],
            "expected_topics": ["credit", "score", "history", "risk"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "risk_assessment",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "What's the LTV for this application?"},
        "expectations": {
            "expected_answer": "LTV",
            "expected_tools": ["uw_risk_assessment"],
            "expected_topics": ["LTV", "loan", "value", "property"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "risk_assessment",
            "complexity": "simple",
            "tool_required": True,
        },
    },
    # Compliance
    {
        "inputs": {"user_message": "Run a compliance check on application 667"},
        "expectations": {
            "expected_answer": "compliance",
            "expected_tools": ["uw_compliance_check"],
            "expected_topics": ["compliance", "TRID", "regulation"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "compliance",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "Are there any fair lending concerns?"},
        "expectations": {
            "expected_answer": "fair lending",
            "expected_tools": ["uw_compliance_check"],
            "expected_topics": ["fair", "lending", "ECOA", "discrimination"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "compliance",
            "complexity": "complex",
            "tool_required": True,
        },
    },
    # Conditions
    {
        "inputs": {"user_message": "What conditions are outstanding for application 667?"},
        "expectations": {
            "expected_answer": "condition",
            "expected_tools": ["uw_list_conditions"],
            "expected_topics": ["condition", "outstanding", "required"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "conditions",
            "complexity": "simple",
            "tool_required": True,
        },
    },
    {
        "inputs": {
            "user_message": "Add a condition for updated income verification"
        },
        "expectations": {
            "expected_answer": "condition",
            "expected_tools": ["uw_add_condition"],
            "expected_topics": ["condition", "add", "income", "verification"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "conditions",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    # Decisions
    {
        "inputs": {"user_message": "Approve application 667 with conditions"},
        "expectations": {
            "expected_answer": "approve",
            "expected_tools": ["uw_decision"],
            "expected_topics": ["approve", "decision", "condition"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "decision",
            "complexity": "complex",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "Suspend application 667 pending additional docs"},
        "expectations": {
            "expected_answer": "suspend",
            "expected_tools": ["uw_decision"],
            "expected_topics": ["suspend", "pending", "document"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "decision",
            "complexity": "complex",
            "tool_required": True,
        },
    },
    # Fraud Detection
    {
        "inputs": {"user_message": "Are there any fraud alerts for this application?"},
        "expectations": {
            "expected_answer": "fraud",
            "expected_tools": ["uw_fraud_check"],
            "expected_topics": ["fraud", "alert", "risk", "verification"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "fraud",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
]
