# 11: Real backends: self-hosted text model and speech recognition, the gated hosted comparison, and the recorded evaluation

**Track:** inference

**What to build:** The text model adapter gains a self-hosted implementation speaking to a local inference server, and the speech adapter gains a self-hosted recogniser; both run only in an explicitly launched evaluation configuration on the fictional cast. A hosted-inference adapter (Ollama Cloud was named) exists for the comparison only, refuses to start outside that configuration, and runs only with the operator's own account. The ticket records, in the repository, which models were tried on which hardware, with German quality and latency on the three fictional cases, and the verified terms and actual pricing of the hosted provider before the comparison runs.

**Blocked by:** 01 (Scaffold), 02 (Environments), 05, 06, 07, 08, 09 (Visit review and background), 10 (Dictation)

**Status:** ready-for-agent

**Spec:** PRD story 25, 25a, 41; ADR 0003 (self-hosted default, hosted comparison on the fictional cast only, unverified claims), ADR 0007 (evaluation configuration is never the default of any tier).

## Acceptance criteria

- [ ] A self-hosted text model adapter talks to a local inference server on the same host or network; the product configuration offers only the fixture model and the self-hosted model; there is no fallback from one to another.
- [ ] A self-hosted speech adapter (candidates from the research: whisper.cpp, faster-whisper) transcribes German audio locally; audio stays transient.
- [ ] A separate evaluation configuration, launched explicitly and never the default of the throwaway, test or production tiers, enables the real backends; it refuses to start if the database contains anything but the fictional cast.
- [ ] The hosted-inference adapter starts only inside the evaluation configuration, with an account key supplied by the operator at launch and never committed; outside that configuration it refuses to start with a plain message; speech recognition stays self-hosted in every configuration.
- [ ] Before the hosted comparison runs, the repository records the provider's verified terms (inference regions and any EU-only option, data retention, training on inputs, subprocessors, DPA availability) and the actual price per token, each with its source; where no source exists the item is written as unverified, not as a fact in either direction.
- [ ] The evaluation record names the hardware, the models and versions tried, and for each of the three fictional cases (assessment and visits, typed notes and canned-transcript dictation) the German output quality against the fixture expectations and the latency; a model that cannot carry the workflow is reported as such.
- [ ] Operator-run, before merge: on the chosen inference hardware, the operator launches the evaluation configuration, runs the self-hosted model and recogniser against the fictional cast and, with their own account, the hosted comparison, and confirms the recorded numbers; the operator approves the comparison run and any spend beforehand.
- [ ] Automated tests keep using the stand-ins; a test asserts that the hosted adapter refuses to start outside the evaluation configuration and that the evaluation configuration refuses non-fictional data.
- [ ] Unslop: the unslop skill and `references/signs.md` were read before work for the changed documentation and any UI; the proof names the signs checked and remaining findings with reasons.
