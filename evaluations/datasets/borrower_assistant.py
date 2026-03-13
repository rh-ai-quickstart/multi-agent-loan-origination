# This project was developed with assistance from AI tools.
"""Evaluation dataset for Borrower Assistant (Authenticated Borrower persona).

The borrower assistant helps authenticated borrowers with:
- Application management (start, update, status)
- Document tracking (completeness, processing status)
- Condition management (list, respond, check satisfaction)
- Disclosure acknowledgment
- Rate lock status
- Pre-qualification estimates
"""

BORROWER_ASSISTANT_DATASET = [
    # Application Status Queries
    {
        "inputs": {"user_message": "What's my application status?"},
        "expectations": {
            "expected_answer": "application",
            "expected_tools": ["application_status", "list_my_applications"],
            "expected_topics": ["status", "stage", "processing"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "status",
            "complexity": "simple",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "Show me a summary of my application"},
        "expectations": {
            "expected_answer": "application",
            "expected_tools": ["get_application_summary"],
            "expected_topics": ["summary", "progress", "collected"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "status",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    # Document Queries
    {
        "inputs": {"user_message": "What documents do I still need to upload?"},
        "expectations": {
            "expected_answer": "document",
            "expected_tools": ["document_completeness"],
            "expected_topics": ["upload", "required", "missing"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "documents",
            "complexity": "simple",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "I uploaded my pay stubs. What's the status?"},
        "expectations": {
            "expected_answer": "document",
            "expected_tools": ["document_processing_status"],
            "expected_topics": ["processing", "status", "uploaded"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "documents",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    # Condition Queries
    {
        "inputs": {"user_message": "What are my underwriting conditions?"},
        "expectations": {
            "expected_answer": "condition",
            "expected_tools": ["list_conditions"],
            "expected_topics": ["condition", "underwriting", "required"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "conditions",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    {
        "inputs": {
            "user_message": "I need to respond to the income verification condition"
        },
        "expectations": {
            "expected_answer": "condition",
            "expected_tools": ["respond_to_condition_tool", "list_conditions"],
            "expected_topics": ["response", "condition", "income"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "conditions",
            "complexity": "complex",
            "tool_required": True,
        },
    },
    # Rate Lock Queries
    {
        "inputs": {"user_message": "When does my rate lock expire?"},
        "expectations": {
            "expected_answer": "rate",
            "expected_tools": ["rate_lock_status"],
            "expected_topics": ["rate lock", "expire", "days"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "rates",
            "complexity": "simple",
            "tool_required": True,
        },
    },
    # Application Workflow
    {
        "inputs": {"user_message": "I want to start a new mortgage application"},
        "expectations": {
            "expected_answer": "application",
            "expected_tools": ["start_application"],
            "expected_topics": ["start", "application", "begin"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "workflow",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "Can I update my income information?"},
        "expectations": {
            "expected_answer": "update",
            "expected_tools": ["update_application_data"],
            "expected_topics": ["update", "income", "application"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "data_update",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    # Disclosure Queries
    {
        "inputs": {"user_message": "What disclosures do I need to sign?"},
        "expectations": {
            "expected_answer": "disclosure",
            "expected_tools": ["disclosure_status"],
            "expected_topics": ["disclosure", "acknowledge", "sign"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "compliance",
            "complexity": "simple",
            "tool_required": True,
        },
    },
]
