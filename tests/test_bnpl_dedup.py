"""Tests for BNPL deduplication."""
from datetime import date

from models.schema import BNPLPlan, BNPLInstallment
from sqlmodel import select

from services.bnpl_dedup import (
    deduplicate, find_duplicate_installments, find_duplicate_plans,
)


def _add_plan(session, **kw):
    defaults = {
        "source": "manual", "provider": "klarna", "merchant_name": "dstnc",
        "original_amount": 122.76, "total_payments": 9, "payment_amount": 13.64,
        "cadence": "biweekly", "start_date": date(2026, 6, 7), "is_active": True,
    }
    defaults.update(kw)
    plan = BNPLPlan(**defaults)
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def _add_inst(session, plan_id, num, due, amount=13.64):
    session.add(BNPLInstallment(
        plan_id=plan_id, installment_number=num,
        due_date=due, amount=amount, status="scheduled",
    ))
    session.commit()


def test_no_duplicates_returns_empty(session):
    plan = _add_plan(session)
    _add_inst(session, plan.id, 1, date(2026, 6, 7))
    _add_inst(session, plan.id, 2, date(2026, 6, 21))
    assert find_duplicate_installments(session) == []
    assert find_duplicate_plans(session) == []


def test_finds_duplicate_installment_rows(session):
    plan = _add_plan(session)
    _add_inst(session, plan.id, 1, date(2026, 6, 7))
    _add_inst(session, plan.id, 1, date(2026, 6, 7))  # exact dupe
    _add_inst(session, plan.id, 1, date(2026, 6, 7))  # second dupe
    dupes = find_duplicate_installments(session)
    assert len(dupes) == 2  # 3 rows total, 2 are duplicates of the kept one


def test_finds_duplicate_plans(session):
    _add_plan(session)
    _add_plan(session)  # same key, different id
    _add_plan(session)  # third dupe
    dupes = find_duplicate_plans(session)
    assert len(dupes) == 2


def test_deduplicate_removes_duplicate_installments(session):
    plan = _add_plan(session)
    _add_inst(session, plan.id, 1, date(2026, 6, 7))
    _add_inst(session, plan.id, 1, date(2026, 6, 7))
    _add_inst(session, plan.id, 2, date(2026, 6, 21))

    result = deduplicate(session)
    assert result["installments_removed"] == 1

    remaining = session.exec(select(BNPLInstallment)).all()
    assert len(remaining) == 2
    # Both numbers still present
    nums = sorted([i.installment_number for i in remaining])
    assert nums == [1, 2]


def test_deduplicate_consolidates_duplicate_plans(session):
    """Two identical plans, installments under each — should merge to one plan."""
    p1 = _add_plan(session)
    _add_inst(session, p1.id, 1, date(2026, 6, 7))
    _add_inst(session, p1.id, 2, date(2026, 6, 21))

    p2 = _add_plan(session)  # exact duplicate plan
    _add_inst(session, p2.id, 1, date(2026, 6, 7))  # duplicate #1 under dup plan
    _add_inst(session, p2.id, 2, date(2026, 6, 21))

    result = deduplicate(session)
    assert result["plans_removed"] == 1
    # After re-pointing + dedup: only one plan, only 2 installments
    plans = session.exec(select(BNPLPlan)).all()
    assert len(plans) == 1
    insts = session.exec(select(BNPLInstallment)).all()
    assert len(insts) == 2
    # All point at the kept plan
    keep_id = plans[0].id
    assert all(i.plan_id == keep_id for i in insts)


def test_deduplicate_idempotent(session):
    """Running dedupe twice should leave the data unchanged after the first run."""
    plan = _add_plan(session)
    _add_inst(session, plan.id, 1, date(2026, 6, 7))
    _add_inst(session, plan.id, 1, date(2026, 6, 7))

    first = deduplicate(session)
    assert first["installments_removed"] == 1

    second = deduplicate(session)
    assert second["installments_removed"] == 0
    assert second["plans_removed"] == 0
