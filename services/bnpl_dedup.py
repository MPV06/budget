"""Deduplicate BNPL installments + plans.

Background: the bnplinstallment table has no UNIQUE constraint on
(plan_id, installment_number), so repeated imports or accidental
double-submits can leave duplicate rows. This module finds and removes them.

Strategy:
  - For plans: dedupe by (provider, merchant_name, payment_amount,
    total_payments, cadence, start_date). Keep MIN(id), drop rest.
  - For installments: dedupe by (plan_id, installment_number) AFTER plan
    dedup. Keep MIN(id), drop rest. Re-point any FK references first.
"""
from collections import defaultdict
from typing import Dict, List, Tuple

from sqlmodel import Session, select

from models.schema import BNPLPlan, BNPLInstallment


def find_duplicate_installments(session: Session) -> List[Tuple[int, int, int]]:
    """Return [(plan_id, installment_number, duplicate_row_id), ...].

    For each (plan_id, installment_number) group, lists every row id EXCEPT
    the minimum (which is kept).
    """
    rows = session.exec(select(BNPLInstallment)).all()
    groups: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for r in rows:
        groups[(r.plan_id, r.installment_number)].append(r.id)

    duplicates: List[Tuple[int, int, int]] = []
    for (plan_id, num), ids in groups.items():
        if len(ids) > 1:
            keep = min(ids)
            for dup_id in ids:
                if dup_id != keep:
                    duplicates.append((plan_id, num, dup_id))
    return duplicates


def find_duplicate_plans(session: Session) -> List[Tuple[Tuple, int]]:
    """Return [(plan_key, duplicate_plan_id), ...].

    plan_key = (provider, merchant_name, payment_amount, total_payments,
                cadence, start_date)
    """
    rows = session.exec(select(BNPLPlan)).all()
    groups: Dict[Tuple, List[int]] = defaultdict(list)
    for r in rows:
        key = (r.provider, r.merchant_name, round(r.payment_amount, 4),
               r.total_payments, r.cadence, r.start_date)
        groups[key].append(r.id)

    duplicates: List[Tuple[Tuple, int]] = []
    for key, ids in groups.items():
        if len(ids) > 1:
            keep = min(ids)
            for dup_id in ids:
                if dup_id != keep:
                    duplicates.append((key, dup_id))
    return duplicates


def deduplicate(session: Session) -> Dict[str, int]:
    """Remove duplicate plans + installments. Returns counts removed.

    Order matters:
      1. Find duplicate plans → re-point any installments under dupe-plan ids
         to the kept plan id
      2. Delete the duplicate plan rows
      3. Find duplicate installments (now that plan_ids are consolidated)
      4. Delete duplicate installment rows
    """
    # ─── Plan dedup ──
    plan_dupes = find_duplicate_plans(session)
    # Build dup_id → keep_id map for installment re-pointing
    plans = list(session.exec(select(BNPLPlan)).all())
    by_key: Dict[Tuple, List[BNPLPlan]] = defaultdict(list)
    for p in plans:
        key = (p.provider, p.merchant_name, round(p.payment_amount, 4),
               p.total_payments, p.cadence, p.start_date)
        by_key[key].append(p)
    dup_to_keep: Dict[int, int] = {}
    for key, group in by_key.items():
        if len(group) > 1:
            sorted_group = sorted(group, key=lambda p: p.id)
            keep_id = sorted_group[0].id
            for p in sorted_group[1:]:
                dup_to_keep[p.id] = keep_id

    # Re-point installments under dup plans to the kept plan
    if dup_to_keep:
        all_installments = session.exec(select(BNPLInstallment)).all()
        for inst in all_installments:
            if inst.plan_id in dup_to_keep:
                inst.plan_id = dup_to_keep[inst.plan_id]
                session.add(inst)
        session.commit()

    # Delete duplicate plans
    plans_removed = 0
    if dup_to_keep:
        for dup_id in dup_to_keep:
            plan = session.get(BNPLPlan, dup_id)
            if plan is not None:
                session.delete(plan)
                plans_removed += 1
        session.commit()

    # ─── Installment dedup (after plan consolidation) ──
    inst_dupes = find_duplicate_installments(session)
    insts_removed = 0
    for plan_id, num, dup_id in inst_dupes:
        inst = session.get(BNPLInstallment, dup_id)
        if inst is not None:
            session.delete(inst)
            insts_removed += 1
    session.commit()

    return {"plans_removed": plans_removed, "installments_removed": insts_removed}
