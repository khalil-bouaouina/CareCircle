"""HTTP layer, thin: parse the request, call a service, return. No logic here.

Statement reads never touch ``repositories.statements`` from a route; they call
``services.visibility.resolve``.

Templates are not built yet. Handlers accept the form field names the guide
fixes (``completion``, ``observation_codes``, ``note_text``, ``visible_to``,
``applies_to_tasks`` ...) and return JSON, so the Jinja layer can be added later
without changing anything here.
"""

from __future__ import annotations

from ..models import Checkout, Proposal, Statement, Visit


def statement_out(s: Statement) -> dict:
    return s.to_dict()


def checkout_out(c: Checkout | None) -> dict | None:
    return c.to_dict() if c else None


def visit_out(v: Visit, checkout: Checkout | None = None, has_brief: bool = False) -> dict:
    d = v.to_dict()
    d.pop("token_hash", None)
    d["has_brief"] = has_brief
    d["checkout"] = checkout_out(checkout)
    return d


def proposal_out(p: Proposal) -> dict:
    return p.to_dict()
