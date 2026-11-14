"""
Record staff changes to orders, payments, prices, and refunds.

The current user is taken from the request. Shopper actions and provider
webhooks have no staff actor, so they are not written here.
"""

import contextvars
import logging
from decimal import Decimal

_actor = contextvars.ContextVar("staff_audit_actor", default=None)
logger = logging.getLogger("endoville.staff_audit")


def set_audit_user(user):
    return _actor.set(user)


def reset_audit_user(token):
    _actor.reset(token)


def get_audit_user():
    user = _actor.get()
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if not getattr(user, "is_staff", False):
        return None
    return user


def money(value):
    if value is None or value == "":
        return None
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


def log_staff_change(*, action, target_type, target_id, summary, changes=None, order_id=None):
    """
    Persist one staff change. Returns the row, or None when no staff user is on the request.
    """
    actor = get_audit_user()
    if actor is None:
        return None

    from users.models import StaffChangeLog

    row = StaffChangeLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        order_id=order_id,
        summary=summary[:255],
        changes=changes or {},
    )
    logger.info(
        "staff_change action=%s target=%s:%s actor=%s order=%s summary=%s",
        action,
        target_type,
        target_id,
        actor.pk,
        order_id,
        summary,
    )
    return row
