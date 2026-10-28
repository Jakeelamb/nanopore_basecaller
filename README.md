# Reference-assisted prefix feedback

This research framework adds bounded reference feedback to Dorado-derived CRF scores. **Biological improvement over stock Dorado is not established.** The current evidence qualifies specific integration and scoring contracts; it does not qualify a replacement basecaller.

The native decoder keeps an independent signal-only branch alongside its contextual branch. Reference locations come from provisional prefixes. Unscored indel proposals enter a separate candidate union, and policy selection preserves the original free winner. Source, input, state, release, and command identities bind each transition.

Start with the [current evidence and limits](research/completion-evidence.md). Earlier readiness documents describe their named historical source cuts.

| Task | Entry point |
| --- | --- |
| Inspect the native decoder and its controls | [Prefix feedback](tools/prefix_feedback/README.md) |
| Consume a retained genuine advance through F1/F3/F2 | [Handoff protocol](research/genuine-prefix-handoff.md) |
| Map a prefix and consume the next reference update | [Retained feedback verification](research/prefix-feedback-verifier.md) |
| Check exact uniform-prefix likelihood independently | [Rust scalar oracle](tools/prefix_scalar_oracle/README.md) |

Run the portable metadata contracts with Python 3.12.8 and UV:

```sh
uv run --no-project --python 3.12.8 python -B tests/run_cpu_contracts.py
```

The [`cpu-contracts` workflow](.github/workflows/verify.yml) also runs the independent Rust synthetic and custody controls with pinned nightly `2026-10-25`. Its assertions and zero-skip requirement are explicit. CPU CI does not execute genuine native sequencing or validate biological accuracy.

Native acceptance uses frozen local source/data manifests and the existing F4 supervisor. Mapping admits at most two CPUs, 16 GiB RAM, 24 GiB address space, and 300 seconds; engineering units use 4 GiB RAM and 8 GiB address space. Both use the canonical nonblocking host lock and retain command, exit, clock, raw output, and cleanup evidence. The protocols name the required paths and exact grants; the scripts do not acquire scientific execution authority themselves.

Runtime dependencies remain separate reviewed lanes: [F1](https://github.com/Jakeelamb/nanopore_basecaller/pull/16), [F2](https://github.com/Jakeelamb/nanopore_basecaller/pull/18), [F3](https://github.com/Jakeelamb/nanopore_basecaller/pull/17), and [F4](https://github.com/Jakeelamb/nanopore_basecaller/pull/19). This checkout includes F1 and the new verification tools. A native run also needs the pinned sibling executables and external inputs; a clean checkout alone does not supply those assets.

Raw signals, references, truth, weights, binaries, and generated results stay outside Git. Stock controls remain unchanged. HG005 results cannot select this candidate. Promotion still needs complete matched stock/candidate processing, private-allele safety, a qualified independent holdout, and the predeclared biological endpoints.
