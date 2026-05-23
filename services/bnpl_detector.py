import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from dateutil.relativedelta import relativedelta

_PATTERNS = [
    (re.compile(r"chase\s*pay[\s\-]?in[\s\-]?4", re.I), "chase_pay_in_4"),
    (re.compile(r"\baffirm\b", re.I), "affirm"),
    (re.compile(r"\bklarna\b", re.I), "klarna"),
    (re.compile(r"\bafterpay\b", re.I), "afterpay"),
]


def detect_provider(description: str) -> Optional[str]:
    for pattern, provider in _PATTERNS:
        if pattern.search(description):
            return provider
    return None


@dataclass
class ProjectedInstallment:
    installment_number: int
    due_date: date
    amount: float


def project_schedule(
    start: date,
    total_payments: int,
    payment_amount: float,
    cadence: str,
) -> List[ProjectedInstallment]:
    if cadence not in {"biweekly", "monthly"}:
        raise ValueError(f"Unsupported cadence: {cadence}")
    result = []
    for i in range(total_payments):
        if cadence == "biweekly":
            due = start + timedelta(days=14 * i)
        else:
            due = start + relativedelta(months=i)
        result.append(ProjectedInstallment(
            installment_number=i + 1,
            due_date=due,
            amount=round(payment_amount, 2),
        ))
    return result
