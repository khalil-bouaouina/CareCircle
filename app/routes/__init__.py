"""HTTP layer, thin: parse the request, call a service, render a template.
No logic here.

The one rule that keeps this clean: routes never call ``repositories.statements``
for a read. They call ``services.visibility.resolve``.
"""

ELDER_ID = 1  # single-elder demo; production would take this from the session
