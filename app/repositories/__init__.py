"""Every SQL statement in the project lives in this package (B5-B10).

Functions take and return dataclasses or primitives, never ``sqlite3.Row``.
No function here contains an ``if`` that expresses a policy -- policy lives in
``services/``. There is no delete function in ``access_log`` or ``checkouts``:
append-only is enforced by absence.
"""
