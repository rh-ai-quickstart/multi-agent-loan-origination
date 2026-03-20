# This project was developed with assistance from AI tools.
"""Simplified evaluation dataset for Public Assistant (Prospect persona).

This is a baseline dataset with straightforward test cases.
Uses the same structure as the working evaluations.
"""

PUBLIC_ASSISTANT_SIMPLE_DATASET = [
    # Product Information - Simple Questions
    {
        "inputs": {"user_message": "What loan products do you offer?"},
        "expectations": {
            "expected_answer": "30-year",
            "expected_tool_calls": [{"name": "product_info"}],  # MLflow format
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
    # Affordability - With enough info for tool to be called
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
