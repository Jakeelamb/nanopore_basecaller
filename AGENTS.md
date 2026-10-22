READ /home/jake/Projects/agent-scripts/AGENTS.MD BEFORE ANYTHING, if present.

For Poteto Mode, read `/home/jake/.agents/skills/poteto-mode/SKILL.md`, if present.

## Changes and evidence

Use feature branches and pull requests targeting `main`. Do not push changes directly to `main` after the repository's initial policy commit. Preserve unrelated work. Do not merge a pull request without authorization.

Use `uv` for project Python commands. Native Dorado and samtools perform sequencing computation. Python coordinates tools and validates their outputs. Prefer Rust for new substantial computation.

Keep raw signals, references, truth files, model weights, software distributions, and generated results outside Git. Commit manifests, source pins, protocols, verification scripts, tests, and concise evidence summaries. Preserve local raw command receipts and failed attempts.

Stock controls remain unchanged. Put future candidate changes in separate paths and predeclare their hypothesis and endpoint. Development and validation support candidate selection. Do not select candidates using HG005 results.

Run checks appropriate to the change and record exact commands and outcomes in the pull request. CPU CI verifies only its listed contracts. Native GPU, full reference, complete input processing, biological accuracy, and performance claims each require their own evidence. Never infer them from CI passing.
