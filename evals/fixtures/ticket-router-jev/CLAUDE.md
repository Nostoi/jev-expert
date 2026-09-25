# ticket-router

Routes inbound support tickets to team queues and pages on-call for urgent ones.

- Tests: `uv run pytest`
- Settings come from environment variables via `ticket_router/config.py`; add new
  settings there, not with ad-hoc `os.environ` reads.
- Side effects (paging, auto-replies) live only in `ticket_router/actions.py`.
- Use the `logging` module (logger per module); no prints.
