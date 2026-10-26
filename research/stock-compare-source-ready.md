# F4 source review and proposed CPU units

Tests actually executed:0. All commands below are prospective and require Root's fresh exact admission. No lock was attempted. Source freeze includes only F4 owned paths. The adapter is a review candidate, not a qualified primitive.

Cwd for every command: `/home/jake/Projects/nanopore_basecaller-next-stock-compare`.
Fixed environment: `UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1`. Absolute uv is `/home/jake/.local/bin/uv`. Root request env must additionally supply the existing user-session `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`, `PATH`, `HOME` and deterministic `LC_ALL=C`; no new environment or network.

Exact focused CPU argv:

```
/home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python -m unittest discover -s /home/jake/Projects/nanopore_basecaller-next-stock-compare/tests -p test_stock_feedback.py -v
```

External boundary/canary argv (request and digest authored by Root after source review):

```
/home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python /home/jake/Projects/nanopore_basecaller-next-stock-compare/tools/stock_feedback/bounded.py run --request <absolute-root-grant.json> --request-sha256 <root-grant-sha256> --output /home/jake/Projects/nanopore_basecaller-next-stock-compare/results/stock-feedback/qualification-01
```

The grant's argv is exactly the focused CPU argv above. Grant schema is bounded-command/1; required fields are demonstrated by `StockFeedback.request()` in tests. Root sets a fresh id/not_before_utc/expires_utc and exact root=cwd above. Caps: profileengineering, wall300s, CPU2, memory4294967296, AS8589934592, swap0, growth104857600, aggregate4294967296, reserve32212254720. Explicit source_pins must include the entire owned source census plus uv/interpreter, /usr/bin/time, and original GUARD. Exact input_pins is empty for these hermetic synthetic controls. expected_files must be the new qualification output's stdout/stderr/time.txt. output_roots must include the absolute results/stock-feedback parent and any separate owned output directory; those parents must exist before launch. Never reuse an existing output attempt or grant id.

Required genuine canary: this one real systemd unit must run tests without skips; kernel.json must prove actual memory.max/cpu.max/swap.max/RLIMIT_AS, outer-terminal.json must show terminal unit and cgroup-empty before lock release, terminal.json must bind raw child exit, and complete.json must link full raw stdout/stderr/time. Test original_guard_ignored_TERM_descendant_after_leader_exit must record/observe the actual descendant cleanup and unrelated survivor. Existing historical receipts cannot substitute. The adapter is not qualified merely because isolated Python fixtures pass.

A separate mapping-profile canary, only after engineering admission, uses identical synthetic test argv and profilemapping/RAM17179869184/AS25769803776, CPU2/swap0, same wall/output caps. The negative ordinary4/8 versus mapping16/24 mismatch is a focused driver validation control; actual kernel_check is a separate guard. No mapper or native producer runs in either canary.

Comparison CLI argv uses the same fixed uv prefix:

```
python /home/jake/Projects/nanopore_basecaller-next-stock-compare/scripts/stock-feedback-compare.py inventory --config /home/jake/Projects/nanopore_basecaller-next-stock-compare/config/stock-feedback-compare-v1.json --output <fresh-inventory.json>
python /home/jake/Projects/nanopore_basecaller-next-stock-compare/scripts/stock-feedback-compare.py plan --config /home/jake/Projects/nanopore_basecaller-next-stock-compare/config/stock-feedback-compare-v1.json --output <fresh-plan.json>
python /home/jake/Projects/nanopore_basecaller-next-stock-compare/scripts/stock-feedback-compare.py report --config /home/jake/Projects/nanopore_basecaller-next-stock-compare/config/stock-feedback-compare-v1.json --plan <frozen-plan.json> --output <fresh-report.json>
python /home/jake/Projects/nanopore_basecaller-next-stock-compare/scripts/stock-feedback-compare.py run --request <absolute-root-grant.json> --request-sha256 <root-grant-sha256> --output <fresh-attempt-directory>
```

Plan/report without supplied closures intentionally return every original parent in an unqualified matrix. A later qualified supplied-arm JSON must bind all original input/model/tool/domain pins and exact source/input/argv/cwd tuple. Prospective native SUP science remains held: before proposing basecall changes, close whether an existing compatible producer can be reused. If absent, return its exact required settings and source/native/model pins for separate Root review; no replay/download is permitted from this source cut.
