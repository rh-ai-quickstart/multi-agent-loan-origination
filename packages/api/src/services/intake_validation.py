# This project was developed with assistance from AI tools.
"""Field-level validation for mortgage application intake.

Pure functions that validate and normalize individual field values
collected during conversational intake.
"""

import re
from collections.abc import Callable
from datetime import date, datetime


def validate_ssn(value: str) -> tuple[bool, str, str | None]:
    """Validate and normalize SSN to XXX-XX-XXXX format."""
    digits = re.sub(r"[\s\-]", "", value.strip())
    if not re.fullmatch(r"\d{9}", digits):
        return False, "SSN must be 9 digits (XXX-XX-XXXX)", None
    if digits in ("000000000", "111111111", "123456789"):
        return False, "SSN appears invalid", None
    normalized = f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
    return True, "", normalized


def validate_dob(value: str) -> tuple[bool, str, str | None]:
    """Validate date of birth. Accepts multiple formats."""
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y"]
    parsed: date | None = None
    for fmt in formats:
        try:
            parsed = datetime.strptime(value.strip(), fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        return False, "Could not parse date. Try MM/DD/YYYY or YYYY-MM-DD.", None

    today = date.today()
    age = today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))
    if age < 18:
        return False, "Applicant must be at least 18 years old", None
    if age > 120:
        return False, "Date of birth appears invalid", None
    return True, "", parsed.isoformat()


def validate_email(value: str) -> tuple[bool, str, str | None]:
    """Basic email format validation."""
    value = value.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        return False, "Invalid email format", None
    return True, "", value


def validate_income(value: str) -> tuple[bool, str, str | None]:
    """Validate gross monthly income."""
    cleaned = re.sub(r"[$,\s]", "", value.strip())
    try:
        amount = float(cleaned)
    except ValueError:
        return False, "Could not parse income amount", None
    if amount < 0:
        return False, "Income cannot be negative", None
    if amount > 4_200_000:  # $50M/yr = $4.17M/mo
        return False, "Income seems unusually high -- please confirm", None
    return True, "", f"{amount:.2f}"


def validate_monthly_debts(value: str) -> tuple[bool, str, str | None]:
    """Validate monthly debt obligations."""
    cleaned = re.sub(r"[$,\s]", "", value.strip())
    try:
        amount = float(cleaned)
    except ValueError:
        return False, "Could not parse debt amount", None
    if amount < 0:
        return False, "Debt amount cannot be negative", None
    return True, "", f"{amount:.2f}"


def validate_total_assets(value: str) -> tuple[bool, str, str | None]:
    """Validate total assets."""
    cleaned = re.sub(r"[$,\s]", "", value.strip())
    try:
        amount = float(cleaned)
    except ValueError:
        return False, "Could not parse asset amount", None
    if amount < 0:
        return False, "Asset amount cannot be negative", None
    return True, "", f"{amount:.2f}"


def validate_loan_amount(value: str) -> tuple[bool, str, str | None]:
    """Validate requested loan amount."""
    cleaned = re.sub(r"[$,\s]", "", value.strip())
    try:
        amount = float(cleaned)
    except ValueError:
        return False, "Could not parse loan amount", None
    if amount <= 0:
        return False, "Loan amount must be positive", None
    if amount > 100_000_000:
        return False, "Loan amount exceeds maximum", None
    return True, "", f"{amount:.2f}"


def validate_property_value(value: str) -> tuple[bool, str, str | None]:
    """Validate property value."""
    cleaned = re.sub(r"[$,\s]", "", value.strip())
    try:
        amount = float(cleaned)
    except ValueError:
        return False, "Could not parse property value", None
    if amount <= 0:
        return False, "Property value must be positive", None
    return True, "", f"{amount:.2f}"


def validate_credit_score(value: str) -> tuple[bool, str, str | None]:
    """Validate credit score (300-850)."""
    cleaned = value.strip()
    try:
        score = int(cleaned)
    except ValueError:
        return False, "Credit score must be a number", None
    if score < 300 or score > 850:
        return False, "Credit score must be between 300 and 850", None
    return True, "", str(score)


def validate_loan_type(value: str) -> tuple[bool, str, str | None]:
    """Validate loan type against known types."""
    from db.enums import LoanType

    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    # Common aliases
    aliases = {
        "conventional": "conventional_30",
        "conv_30": "conventional_30",
        "conv_15": "conventional_15",
        "30_year": "conventional_30",
        "15_year": "conventional_15",
        "adjustable": "arm",
        "adjustable_rate": "arm",
        "variable_rate": "arm",
    }
    normalized = aliases.get(normalized, normalized)
    try:
        LoanType(normalized)
        return True, "", normalized
    except ValueError:
        valid = [lt.value for lt in LoanType]
        return False, f"Unknown loan type. Valid: {', '.join(valid)}", None


def validate_employment_status(value: str) -> tuple[bool, str, str | None]:
    """Validate employment status."""
    from db.enums import EmploymentStatus

    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "employed": "w2_employee",
        "w2": "w2_employee",
        "self": "self_employed",
        "freelance": "self_employed",
        "contractor": "self_employed",
        "1099": "self_employed",
    }
    normalized = aliases.get(normalized, normalized)
    try:
        EmploymentStatus(normalized)
        return True, "", normalized
    except ValueError:
        valid = [es.value for es in EmploymentStatus]
        return False, f"Unknown status. Valid: {', '.join(valid)}", None


_VALIDATORS: dict[str, Callable] = {
    "ssn": validate_ssn,
    "date_of_birth": validate_dob,
    "email": validate_email,
    "gross_monthly_income": validate_income,
    "monthly_debts": validate_monthly_debts,
    "total_assets": validate_total_assets,
    "loan_amount": validate_loan_amount,
    "property_value": validate_property_value,
    "credit_score": validate_credit_score,
    "loan_type": validate_loan_type,
    "employment_status": validate_employment_status,
}


def validate_field(field_name: str, value: str) -> tuple[bool, str, str | None]:
    """Validate a single field by name.

    Returns (is_valid, error_message, normalized_value).
    Fields without a dedicated validator pass through as-is.
    """
    validator = _VALIDATORS.get(field_name)
    if validator is None:
        return True, "", value.strip() if isinstance(value, str) else value
    return validator(str(value))
