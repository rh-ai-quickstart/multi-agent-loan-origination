# This project was developed with assistance from AI tools.
"""Evaluation dataset for Loan Officer Assistant.

The loan officer assistant helps LOs with:
- Pipeline management (summary, workload)
- Application review (detail, documents, completeness)
- Document quality management (review, resubmission)
- Underwriting submission (readiness check, submit)
- Communication drafting
- Credit pulls and pre-qualification
- Compliance KB search
"""

LOAN_OFFICER_ASSISTANT_DATASET = [
    # Pipeline Management
    {
        "inputs": {"user_message": "Show me my pipeline"},
        "expectations": {
            "expected_answer": "pipeline",
            "expected_tools": ["lo_pipeline_summary"],
            "expected_topics": ["applications", "stage", "workload"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "pipeline",
            "complexity": "simple",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "How many applications do I have in processing?"},
        "expectations": {
            "expected_answer": "application",
            "expected_tools": ["lo_pipeline_summary"],
            "expected_topics": ["processing", "count", "applications"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "pipeline",
            "complexity": "simple",
            "tool_required": True,
        },
    },
    # Application Review
    {
        "inputs": {"user_message": "Review application 667"},
        "expectations": {
            "expected_answer": "application",
            "expected_tools": ["lo_application_detail"],
            "expected_topics": ["borrower", "loan", "status"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "application_review",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "What documents does application 667 need?"},
        "expectations": {
            "expected_answer": "document",
            "expected_tools": ["lo_document_review", "lo_completeness_check"],
            "expected_topics": ["document", "required", "missing"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "documents",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    # Document Quality
    {
        "inputs": {"user_message": "Does the W-2 document have quality issues?"},
        "expectations": {
            "expected_answer": "quality",
            "expected_tools": ["lo_document_quality"],
            "expected_topics": ["quality", "document", "issue"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "document_quality",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    {
        "inputs": {
            "user_message": "Flag the pay stub document for resubmission - it's illegible"
        },
        "expectations": {
            "expected_answer": "resubmission",
            "expected_tools": ["lo_mark_resubmission"],
            "expected_topics": ["flag", "resubmit", "document"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "document_quality",
            "complexity": "complex",
            "tool_required": True,
        },
    },
    # Underwriting Submission
    {
        "inputs": {"user_message": "Is application 667 ready for underwriting?"},
        "expectations": {
            "expected_answer": "underwriting",
            "expected_tools": ["lo_underwriting_readiness"],
            "expected_topics": ["ready", "underwriting", "checklist"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "underwriting",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "Submit application 667 to underwriting"},
        "expectations": {
            "expected_answer": "submit",
            "expected_tools": ["lo_submit_to_underwriting"],
            "expected_topics": ["submit", "underwriting", "application"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "underwriting",
            "complexity": "complex",
            "tool_required": True,
        },
    },
    # Compliance KB
    {
        "inputs": {"user_message": "What's the DTI limit for conventional loans?"},
        "expectations": {
            "expected_answer": "DTI",
            "expected_tools": ["kb_search"],
            "expected_topics": ["DTI", "ratio", "conventional", "limit"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "compliance",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    # Credit and Pre-qualification
    {
        "inputs": {"user_message": "Pull credit for application 667"},
        "expectations": {
            "expected_answer": "credit",
            "expected_tools": ["lo_pull_credit"],
            "expected_topics": ["credit", "score", "report"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "credit",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
]
