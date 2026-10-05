# Local AI operation and validation

JobForge retrieves saved profile/project evidence relevant to the selected job. Fine-tuning is not part of the current workflow.

## Setup

Configure `.env`:

```env
JOBFORGE_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_FAST_MODEL=qwen3.5:4b
JOBFORGE_AI_TIMEOUT_SECONDS=120
```

Run `ollama list` to confirm the configured models exist. Start Ollama, then JobForge; inspect readiness in Local AI studio. Prepare model loads it before drafting. Switching models adds load time. For Docker, configure a host-accessible Ollama address; container localhost is not the host service.

## Draft and review

Choose a full listing and one French/English outreach channel. Enrich discovered links before drafting. Progress, cancellation, saved versions and unsaved-edit protection are visible. Cancelled work must not publish; cancellation may not instantly free GPU memory. Use one process per database.

Read-only agent review retrieves candidate evidence, selected requirements and career-focus constraints through a fixed tool registry. It cannot send messages, apply or execute arbitrary commands.

## Evaluation

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_local_ai.py --models qwen3.5:4b qwen3.5:9b
```

Outputs remain in ignored `runtime/`. Compare applicant voice, relevant evidence, internship wording, junior suitability, certifications, channel length and latency. Valid output structure is not a factual-accuracy score.

The October 5 review found student wording and excessive mastery claims. Graduation facts and wording checks were corrected. Five revised workflows passed and support outreach passed its targeted retest. Application generation measured about 14 seconds; support outreach about 5 seconds. These are smoke measurements, not latency guarantees.

Review education, dates and project achievements. Credential checks cover selected certifications and CPTS ongoing status, not all invented claims. Every draft/PDF requires review. Fine-tuning would require curated examples and an independent evaluation split.
