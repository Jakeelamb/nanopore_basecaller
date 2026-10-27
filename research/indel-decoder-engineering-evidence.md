# F3 indel decoder engineering evidence

Engineering PASS applies to source `352a749242e89bbbb4fd4b244dee996de1c210e9` and the finite synthetic contract below. One CTest ran all 14 named control groups, and all 7 UV unittest methods passed with zero skips, failures, errors or expected failures. Fourteen groups are not fourteen CTests. Root reported `2080 CLOSED0/384060`; independent retained-artifact verification passed 318 checks. This new document leaves all qualified source, prior reports and config unchanged.

The admitted command ran from `/home/jake/Projects/nanopore_basecaller-next-indel-decoder`:

```sh
/home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python tools/indel_feedback/qualify.py --output /home/jake/Projects/nanopore_basecaller-next-indel-decoder/results/indel-feedback/qualification-03
```

The fixed retrieval environment used offline UV, no Python downloads/bytecode, and an in-root TMPDIR. All five stages exited0: Release configure, parallel2 strict C++23 build, serial format-check, serial CTest with JUnit, and consumed-fixture UV tests with `INDEL_FEEDBACK_BINARY` bound to this attempt's `build/indel-feedback`. Each stage retains raw command/cwd/start/end/exit/stdout/stderr/GNU-time files under `stages/<name>`. Executed controls cover tiny exhaustive CRF path mass, repeated paths, known run lengths, nonrepeat indels, boundaries, reverse orientation, event/base accounting, zero exposure, full edits and invalid input rejection. UV tests consume actual synthetic DGS rows and preserve all 64 synthetic parent rows, including zero exposure. Counter, parent/chunk/tensor, availability/context and independent hash corruptions reject.

The actual worker kernel record shows RAM4GiB, CPU200000/100000, swap0 and soft/hard AS8GiB. The fresh whole-unit contract capped wall300s, growth100MiB, aggregate4GiB and reserve30GiB. Worker and outer terminals report exit0/errornull, no missing records, and launcher/service groups empty before unlock. Deadline expiry and resource saturation were not exercised.

## Retained pins

Paths below are relative to `results/indel-feedback/qualification-03/`. The outer completion pins stage raw files; JUnit and `unittest.json` retain counts. Binary provenance is 558752 bytes, recorded SHA256 `9dbfd5aec82131664c7ffcf89ddbc0910eff8aa8002ebba22dfc360a3f71e2cb`; this document did not rehash or execute the binary.

| Artifact | SHA256 |
|---|---|
| `complete.json` | `46ed9b514ca30f7185d3d1888d5e3a74499f8931f672ee6f5ff7e2ea9e54fff9` |
| `terminal.json` | `726fcc7ea40cb8ed27924531307f6f4ed452765bedde98d05e6f375d3eadf80b` |
| `../qualification-03-outer/complete.json` | `7f9ebbbe1fd68046a8f261880f53b8fedc8703e34b30cbf590b92b36ab9f760d` |
| `../qualification-03-outer/terminal.json` | `a535e6fc3db2f1914807c30ce76f013d08b42e31bf09d755170505aecfce507d` |
| `../qualification-03-outer/outer-terminal.json` | `f5c4901fbee0142056b49547e2666e2c60b7fd803f7f7024f15d6ee53df3eee7` |
| `../qualification-03-outer/kernel.json` | `ea09c66a75d98eca1e37be00a96d4e8f4bdb6f2dd66e3447455ab07a7e38a187` |

The independent report is `/home/jake/Projects/nanopore_basecaller-context-feedback-v3/logs/context-feedback-program/next-four-lanes/reviews/F3-engineering-actual-v1/REPORT.md`, SHA256 `9b5b8ab54da694c9eefc372c096e01fcc5bb42cdd869ab8ed6dd6e70ef190b4a`. Its adjacent `F3-actual.json`, SHA256 `fabe433d98986bf4334c2542d3f57c7209e16615d46dc73aad16799dfa1fa01f`, retains exact checks, source witness, stage argv and evidence pins.

The parent macro directory is `/home/jake/Projects/nanopore_basecaller-retrieval/logs/20261026T201057Z-feedback-f3-qualification-03-NMLRpn/`. Its raw pins are:

| Artifact | SHA256 |
|---|---|
| `command.sh` | `e935c2c295692717d72c560fd348fdfd405587544b03a85b5ca1680aa99109d6` |
| `cwd.txt` | `81780b410cc6ad509f4b54839a9bdec42ed3fcf5c10e6795f8d61ff16a025467` |
| `start.txt` | `b3779b3f103aee84482877feecfa89391692752259c9c5f03860f03bea0d9229` |
| `end.txt` | `2aa00143b40a43f7aa44fe350e07df7933b6e5b0eb0b151c06e1940692f99f26` |
| `exit-status.txt` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| `stdout + stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `time.txt` | `d41b4cd314d9d51b0bb726460b60d5bd993b121ce2c9c50e3bd9e2b86797c338` |

## Preserved failures and next boundary

Earlier attempts remain failed and unchanged. `qualification-01` configured successfully, then failed strict compilation on implicit string/JSON equality. `qualification-02` built and passed format-check, then CTest's default build-directory cwd hit the retained source-root guard before controls ran. Explicit scalar extraction and CTest's canonical source-root working directory were corrected before this fresh successful unit.

F3 is ready for a newly pinned genuine F1 batch, independent binding/hash, released DGS/DGM and native identity, plus a separate unchanged-original-Rust scalar receipt. Its extension sidecar is not a complete F2 batch. F1 must merge it, compute context costs/union NN, normalize replacement edits into the frozen SNV/INS/DEL contract and reconstruct full-parent SEQ/Q. Root must freeze those cross-lane inputs and admit one genuine consumption plus rejection before any pilot.

Genuine cross-lane integration, private/genuine scientific inputs, complete input processing, native Rust parity where required, actual two-domain parent reconciliation, calibration, biological/variant accuracy, speed and promotion remain held. Synthetic engineering PASS supplies no scientific or GPU execution authority. Full compiler/system-header/OpenSSL/user-manager closure and unexercised manager failure paths remain separate limitations.
