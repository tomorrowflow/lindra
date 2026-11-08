---
status: accepted
date: 2026-11-08
---

# A Python web service with SQLite, a responsive browser UI and a single protected user

Lindra is one Python web service with a SQLite database and a German responsive browser UI for iPad and desktop. The text model and speech recognition sit behind swappable adapters (ADR 0003). Access is a private network (Tailscale) plus a single protected application login; there is no registration, no roles and no team accounts. There is no native Apple app and no offline synchronisation.

We chose this because there is one author, the data volume is a handful of cases, and the factory's tooling and environment scripts are Python, so one service and one file database keep the throwaway, test and production stacks identical and trivially resettable. A browser UI reaches the iPad without Apple-platform work, which would have to be routed to the Mac node. Should a later release need the team as authors, roles and a server database become a new decision.

## Considered options

- Native iPad app: rejected for the first release; it doubles the platforms for a single author and needs the Mac node.
- Server database (PostgreSQL): rejected for now; no concurrency and no volume to justify it.

## Consequences

- Autosave and a visible unsaved-changes state replace offline support: on network failure the physician sees what is not saved.
- Everything the physician types or dictates stays on the host that runs the service and its models.
