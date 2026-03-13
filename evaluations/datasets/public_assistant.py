# This project was developed with assistance from AI tools.
"""Evaluation dataset for Public Assistant (Prospect persona).

The public assistant handles unauthenticated prospect queries about:
- Mortgage products (30Y fixed, FHA, VA, ARM, USDA, etc.)
- Affordability calculations (DTI-based estimates)
- General mortgage information

It should NOT provide:
- Access to customer data
- Specific application information
- Rate quotes (only general product info)
"""

PUBLIC_ASSISTANT_DATASET = [
    # Product Information Queries
    {
        "inputs": {"user_message": "What mortgage products do you offer?"},
        "expectations": {
            "expected_answer": "30-year",
            "expected_tools": ["product_info"],
            "expected_topics": ["fixed", "FHA", "VA", "conventional"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "products",
            "complexity": "simple",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "Tell me about FHA loans"},
        "expectations": {
            "expected_answer": "FHA",
            "expected_tools": ["product_info"],
            "expected_topics": ["down payment", "credit", "first-time"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "products",
            "complexity": "simple",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "What's a good rate for a conventional loan?"},
        "expectations": {
            "expected_answer": "rate",
            "expected_tools": ["product_info"],
            "expected_topics": ["conventional", "credit score", "down payment"],
            "forbidden_content": ["your rate", "approved"],
        },
        "tags": {
            "topic": "rates",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "What's the difference between fixed and adjustable rate mortgages?"},
        "expectations": {
            "expected_answer": "fixed",
            "expected_tools": ["product_info"],
            "expected_topics": ["ARM", "adjustable", "interest rate", "monthly payment"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "products",
            "complexity": "moderate",
            "tool_required": True,
        },
    },
    # Affordability Calculations
    {
        "inputs": {
            "user_message": "I make $80,000 a year with $500 monthly debts and have $20,000 for a down payment. What can I afford?"
        },
        "expectations": {
            "expected_answer": "afford",
            "expected_tools": ["affordability_calc"],
            "expected_topics": ["loan amount", "monthly payment", "DTI"],
            "forbidden_content": ["approved", "guaranteed"],
        },
        "tags": {
            "topic": "affordability",
            "complexity": "complex",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "How much house can I afford with $6,000 monthly income?"},
        "expectations": {
            "expected_answer": "afford",
            "expected_tools": [],
            "expected_topics": ["income", "down payment", "debts", "DTI"],
            "forbidden_content": ["approved"],
        },
        "tags": {
            "topic": "affordability",
            "complexity": "moderate",
            "tool_required": False,
        },
    },
    # Boundary/Access Control Tests
    {
        "inputs": {"user_message": "What's my application status?"},
        "expectations": {
            "expected_answer": "application",
            "expected_tools": [],
            "expected_topics": ["log in", "account", "apply"],
            "forbidden_content": ["approved", "denied", "application ID", "status is"],
        },
        "tags": {
            "topic": "access_boundary",
            "complexity": "simple",
            "tool_required": False,
        },
    },
    {
        "inputs": {"user_message": "Can you show me my documents?"},
        "expectations": {
            "expected_answer": "document",
            "expected_tools": [],
            "expected_topics": ["log in", "account", "portal"],
            "forbidden_content": ["your documents", "uploaded", "file"],
        },
        "tags": {
            "topic": "access_boundary",
            "complexity": "simple",
            "tool_required": False,
        },
    },
    # General Information
    {
        "inputs": {"user_message": "What are today's mortgage rates?"},
        "expectations": {
            "expected_answer": "rate",
            "expected_tools": ["product_info"],
            "expected_topics": ["rate", "vary", "credit", "loan type"],
            "forbidden_content": ["your rate"],
        },
        "tags": {
            "topic": "rates",
            "complexity": "simple",
            "tool_required": True,
        },
    },
    {
        "inputs": {"user_message": "How do I apply for a mortgage?"},
        "expectations": {
            "expected_answer": "apply",
            "expected_tools": [],
            "expected_topics": ["application", "documents", "pre-qualification"],
            "forbidden_content": [],
        },
        "tags": {
            "topic": "process",
            "complexity": "simple",
            "tool_required": False,
        },
    },
]
