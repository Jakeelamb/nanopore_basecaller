# Make a change

Create a feature branch from `main`, make one reviewable change, and open a pull request. Include the problem, resulting behavior, validation commands, outcomes, and material limits. Merge through the pull request after review. Keep unsuccessful scientific experiments and their evidence identifiable.

Read `AGENTS.md` and the experiment protocol before changing scientific behavior. Use the locked environment:

```sh
uv sync --locked
uv run --locked python -m unittest discover -s tests -v
```

The complete local suite needs the native tools and space required by the full-reference producer. GitHub CPU checks exercise acquisition, real POD5 decoding, and native BAM contracts without downloading human data or model weights. They do not qualify GPU inference or biological accuracy. Preserve local native qualification receipts when changing the pipeline.

Keep large scientific inputs and generated outputs outside Git. Update the acquisition manifest and protocol when input identity or evaluation rules change. Do not replace existing stock results with candidate results.
