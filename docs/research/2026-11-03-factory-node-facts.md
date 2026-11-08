# Research: factory node facts for the environments decision

Collected on the Linux 3090 node on 3 November 2026 by the SPEC-1 session, from the commands listed.

| Fact | Value | Command |
| --- | --- | --- |
| Hostname | `minisforum3090` | `hostname` |
| Docker Compose | v2.35.1 | `docker compose version` |
| Python | 3.14.4 | `python3 --version` |
| Memory | 76 GB total, about 49 GB available at the time | `free -g` |

Not verified (commands needed approval): rootless Docker daemon details (`docker info`), GPU model and memory (`nvidia-smi`), local Ollama models, existing user timers. The hostname suggests an RTX 3090; the grill should confirm before relying on local inference.

Other factory nodes named on the card: Linux 790, zotac2080, and Mac. None was inspected from this session.
