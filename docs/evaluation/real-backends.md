# Real backends: evaluation record

Ticket LFR-11 (ADR 0003, ADR 0006, ADR 0007). This file records which text models and speech recognisers were tried on which hardware, what they did with the three fictional cases, and what the hosted provider's terms and price are. It uses invented cases only. Real patient data is not used, and nothing here authorises it (ADR 0006).

## Status

The adapters, the evaluation configuration and the measuring tool are built and tested against stand-ins. No real model, recogniser or hosted account has been run yet. The build session had no inference hardware it could use and no web access, so the hardware, model, result and provider sections below are empty or marked unverified. The operator fills them in during the run described under "Operator run".

| Part | State |
| --- | --- |
| Self-hosted text adapter and recogniser adapter | built, tested against a local stub server |
| Evaluation configuration with the cast-only database check | built, tested |
| Hosted comparison adapter | built, tested against a stub, refuses to start outside the evaluation configuration |
| Hardware, models and versions | not recorded, operator run pending |
| Quality and latency per case | not recorded, operator run pending |
| Provider terms and price | unverified, see below |

## How to run

All commands run from the repository root with the project virtualenv. The evaluation configuration is the only place a real backend starts. Nothing else sets `LINDRA_TIER=evaluation`, and `compose.yaml`, `compose.test.yaml`, `compose.prod.yaml` and `scripts/env.py` never mention it.

Self-hosted, with a local inference server that offers the `/v1/chat/completions` route (llama.cpp's server, Ollama and vLLM do) and a recogniser server (whisper.cpp's `whisper-server`, or a faster-whisper server with an OpenAI-style transcription route):

```
.venv/bin/python scripts/evaluation.py serve --data-dir ./eval-data \
  --text-backend selfhosted --text-url http://127.0.0.1:11434 --text-model <model:tag> \
  --speech-backend selfhosted --speech-url http://127.0.0.1:8080
```

For a faster-whisper server add `--speech-path /v1/audio/transcriptions` and `--speech-model <name>`. `serve` refuses to start when the data directory holds a case that is not in the cast, seeds the cast, and prints a login token.

The hosted comparison adds `--text-backend hosted --hosted-url <address> --hosted-model <model> --approved`. The account key goes into the environment variable `LINDRA_HOSTED_KEY`, or the script asks for it on the terminal. It is never read from a file and never printed. `--approved` states that the operator approved the run and its spend. The address is the operator's to give because the provider's endpoint is not verified here (see below).

Measuring, with the recordings described below, writes the tables for the results section:

```
.venv/bin/python scripts/evaluation.py measure --audio-dir ./clips --out run.md \
  --text-backend selfhosted --text-model <model:tag> --speech-backend selfhosted
```

`measure` takes one recording per canned transcript of the cast, named `<clip key>.<extension>`. The five clip keys are in `lindra/cast.py`. The operator reads each canned transcript aloud in German and records it. The transcripts are invented, so the recordings contain no patient data. Without `--audio-dir` only the typed rows are measured.

## What the measuring tool does and does not judge

Each cast encounter goes through the same path as the physician's "Entwurf erzeugen": the model answer is checked for structure, then the fidelity check removes paragraphs the notes do not support. A visit gets the expected drafts of its earlier encounters as background. The dictated rows append the recognised clip to the typed notes as a marked passage, as the product does.

The table columns are mechanical:

| Column | Meaning |
| --- | --- |
| Outcome | `ok`, or `failed:` with the reason the physician would read |
| Seconds | wall time of the generation call |
| Sections filled | sections with at least one paragraph after the fidelity check |
| Unexpected | sections filled where the cast's expected draft has none |
| Paragraphs returned / dropped | what the model returned, and how many the fidelity check removed |
| Passages carried | how many of the notes passages the expected draft rests on came back as input references |
| Gaps flagged | how many of the cast's expected clarification items have an item in the same section |
| WER | word error rate of a recognised clip against its canned transcript |

The tool does not judge German wording, clinical fidelity or fabricated statements. The physician reads each output against the fixture draft in `lindra/cast.py` and records the judgement in the results table. A model that fails on an encounter, or returns none of the passages an encounter rests on, is reported as unable to carry the workflow.

## Hardware

Not recorded. The operator names the chosen inference host here before the run: machine, GPU and memory, operating system, driver, and the server software and version for the text model and for the recogniser. The node facts collected earlier (`docs/research/2026-11-03-factory-node-facts.md`) say only that the hostname suggests an RTX 3090 and that the GPU was never confirmed.

| Item | Value |
| --- | --- |
| Machine | pending |
| GPU and memory | pending |
| Text model server and version | pending |
| Recogniser server and version | pending |

## Models and versions

| Role | Model and version or quantisation | Server | Run |
| --- | --- | --- | --- |
| Self-hosted text model | pending | pending | not run |
| Self-hosted recogniser, whisper.cpp | pending | `whisper-server` | not run |
| Self-hosted recogniser, faster-whisper | pending | pending | not run |
| Hosted text model, comparison | pending | provider's hosted service | not run, see terms |

The research named whisper.cpp and faster-whisper as recogniser candidates. No text model is chosen. Which models the hardware carries, and whether their German is good enough for medical text, is an open question (ADR 0003), and this table is where the answer goes.

Two checks belong in the run. Browsers record webm or mp4, while `whisper-server` reads WAV unless it was started with its conversion option, which needs ffmpeg; check `whisper-server --help` of the installed version. Lindra never writes the recording, but a recogniser server that converts audio may write temporary files on its own host. Record what the installed server does with them.

## Provider terms and price for the hosted comparison

Ollama Cloud was named for the comparison. The operator stated that it offers European inference. That statement is unverified. The comparison must not run before the operator has filled this table from the provider's own published documents, one source per row. Where no source is found, the row says "unverified" and stays that way. A missing assurance is not evidence for or against EU operation or any retention policy (ADR 0003).

The build session could not fetch any provider page, so every row below is unverified and no source is recorded.

| Item | Finding | Source |
| --- | --- | --- |
| Inference regions | unverified | none |
| EU-only option | unverified | none |
| Retention of prompts and outputs | unverified | none |
| Training on inputs | unverified | none |
| Subprocessors | unverified | none |
| Data processing agreement available | unverified | none |
| Price per token, input | unverified | none |
| Price per token, output | unverified | none |
| Whether usage is metered per token at all, or by plan or time | unverified | none |
| Rate limits of the operator's plan | unverified | none |
| Serves an OpenAI-style `/v1/chat/completions` route with a bearer key | unverified | none |

The last row matters for the adapter. It speaks that route, so a provider that offers a different one needs an adapter change before the comparison can run.

Even verified EU hosting would not make the comparison local, and it authorises no real data. The comparison sends only the invented cast.

## Results

One row per case, encounter and mode. Paste the `measure` tables for each configuration under its heading and then fill the judgement columns by reading the outputs. Judgement uses three words: usable, needs edits, unusable. "Fabricated" counts statements in the output that the notes do not contain.

Configurations run, with date and operator: none yet.

| Case | Encounter | Mode | Configuration | Seconds | German quality | Fabricated statements | Lost facts | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FIK-2026-001 | assessment | typed | pending | pending | pending | pending | pending | |
| FIK-2026-001 | assessment | dictated | pending | pending | pending | pending | pending | |
| FIK-2026-001 | visit-1 | typed | pending | pending | pending | pending | pending | |
| FIK-2026-001 | visit-1 | dictated | pending | pending | pending | pending | pending | |
| FIK-2026-002 | assessment | typed | pending | pending | pending | pending | pending | |
| FIK-2026-002 | assessment | dictated | pending | pending | pending | pending | pending | |
| FIK-2026-002 | visit-1 | typed | pending | pending | pending | pending | pending | |
| FIK-2026-002 | visit-2 | typed | pending | pending | pending | pending | pending | |
| FIK-2026-002 | visit-2 | dictated | pending | pending | pending | pending | pending | |
| FIK-2026-003 | assessment | typed | pending | pending | pending | pending | pending | |
| FIK-2026-003 | assessment | dictated | pending | pending | pending | pending | pending | |
| FIK-2026-003 | visit-1 | typed | pending | pending | pending | pending | pending | |

Recogniser clips, from the `measure` output:

| Clip | Configuration | Seconds | WER | Note |
| --- | --- | --- | --- | --- |
| `fik-001-assessment-dictation` | pending | pending | pending | |
| `fik-001-visit-1-dictation` | pending | pending | pending | |
| `fik-002-assessment-dictation` | pending | pending | pending | |
| `fik-002-visit-2-dictation` | pending | pending | pending | |
| `fik-003-assessment-dictation` | pending | pending | pending | |

Verdict per model: pending. A model that cannot carry the workflow is reported as such here, with the encounter where it failed.

## Operator run

Before merge, on the chosen inference hardware:

1. Fill in the hardware table and the model table.
2. Start the evaluation configuration with `serve`, then run `measure` for the self-hosted model and recogniser against the cast. Read the outputs and fill the results tables.
3. Fill the provider table from the provider's own documents. Approve the comparison run and any spend.
4. Run the hosted comparison with your own account and the `--approved` flag, and record it the same way.
5. Comment on the card that you did all of this, with the approved spend, and that the numbers in this file match what you saw.

Until that comment exists the ticket's operator-run item is open.
