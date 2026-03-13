# This project was developed with assistance from AI tools.
"""Evaluation datasets for each agent persona."""

from .borrower_assistant import BORROWER_ASSISTANT_DATASET
from .ceo_assistant import CEO_ASSISTANT_DATASET
from .loan_officer_assistant import LOAN_OFFICER_ASSISTANT_DATASET
from .public_assistant import PUBLIC_ASSISTANT_DATASET
from .underwriter_assistant import UNDERWRITER_ASSISTANT_DATASET

__all__ = [
    "PUBLIC_ASSISTANT_DATASET",
    "BORROWER_ASSISTANT_DATASET",
    "LOAN_OFFICER_ASSISTANT_DATASET",
    "UNDERWRITER_ASSISTANT_DATASET",
    "CEO_ASSISTANT_DATASET",
]
