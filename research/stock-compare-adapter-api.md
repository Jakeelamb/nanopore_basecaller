# Public bounded-command/1 API

Source contract for F1/F2/F3 consumers. NOT QUALIFIED. Root must relay an exact reviewed F4 commit and grant a fresh unit before use. Do not copy the adapter or import/modify the old fixed-ROOT supervisor.

CLI, from the exact admitted cwd:

```
UV_PROJECT_ENVIRONMENT=/home/jake/Projects/nanopore_basecaller-retrieval/.venv UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 /home/jake/.local/bin/uv run --project /home/jake/Projects/nanopore_basecaller-retrieval --no-sync python /home/jake/Projects/nanopore_basecaller-next-stock-compare/tools/stock_feedback/bounded.py run --request <Root-authored-absolute-grant.json> --request-sha256 <Root-grant-SHA256> --output <fresh-absolute-attempt-directory>
```

`run` is the only public execution phase. `worker` is the adapter's systemd intake, not a caller bypass. Root authors the whole request and supplies its SHA256 externally. No lane creates its own grant, consumes an expired grant, or retries a refused canonical lock. Root must create only the output parent before launching; the attempt itself must be absent. Unit id is fresh,64characters maximum, letters/digits/underscore/hyphen. The corresponding systemd unit and cgroup must be absent at preflight.

Required request fields:

| Field | Exact contract |
|---|---|
| schema | `bounded-command/1` |
| id | Fresh Root unit id; service becomes `feedback-next-<id>.service` |
| not_before_utc / expires_utc | Timezone-aware ISO8601 strings; command must start inside this fresh interval |
| root / cwd | Equal absolute canonical existing lane worktree path; actual outer and worker cwd must equal it |
| argv | Exact nonempty string array, no shell; argv[0] absolute executable; use the unchanged mapper/samtools/decoder tool |
| env | Exact child environment map. Required fixed UV variables above; Root supplies existing user-session HOME/PATH/XDG_RUNTIME_DIR/DBUS_SESSION_BUS_ADDRESS and LC_ALL=C as appropriate. No inherited child variables are relied upon |
| source_pins | Full `{path,size,sha256}` pins for frozen adapter, uv/interpreter, /usr/bin/time, original guard and full command/native/source dependency closure. Executable and time pins are mandatory. Paths are canonical absolute paths |
| input_pins | Full `{path,size,sha256}` pins for exactly admitted input files; empty only for a declared hermetic engineering unit |
| expected_files | Nonempty array of absolute successful output/recorder filenames, never just a directory |
| roles | `{unit:"F1/mapper", inputs:{"query-fasta":0,"reference-index":1}, outputs:{"mapped-sam":"<absolute-output>"}}`. Unit must match `F[1-4]/[a-z][a-z0-9-]{0,40}`; input values bijectively cover the input_pins indices; output values exactly cover expected_files. Role names are semantic labels, not permission to substitute another artifact |
| output_roots | Distinct absolute owned directories under root; must include the attempt's parent and every directory the command can grow. The adapter observes these throughout synchronous worker hashing/preparation and command execution |
| profile | `engineering` or `mapping`; exact matching memory/AS values below |
| wall_seconds | At most300, including worker full hashing/preparation/projection. Outer service RuntimeMaxSec subtracts2seconds from remaining admission interval |
| cpus / swap_bytes | Exactly2 /0 |
| memory_bytes / address_space_bytes | engineering4294967296/8589934592; mapping17179869184/25769803776 |
| growth_bytes / aggregate_bytes / reserve_bytes | At most104857600 / exactly4294967296 / exactly32212254720 |

A fixed UV Python orchestration argv begins with `/home/jake/.local/bin/uv`, `run`, `--project`, `/home/jake/Projects/nanopore_basecaller-retrieval`, `--no-sync`, `python`, then the frozen coordinator path and exact arguments. A direct native mapper/samtools/decoder argv begins with its pinned executable and has no shell wrapper. Either is inside /usr/bin/time and the same systemd limits. Any model/reference/POD5 or neural body hashing requires an admitted science role/input pin; source readiness alone does not authorize it.

The worker first validates the externally supplied request hash, request freshness/cwd/profile, actual memory.max/memory.swap.max/cpu.max/RLIMIT_AS and service cgroup identity. It then validates full source/input pins before the command. Child process groups are cleaned through the original pinned process_guard. Worker terminal.json retains clocks/exit/error before successful-output projection. Missing expected_files writes projection-failed.json with producer_replay_permitted=false. A producer that succeeded must not be repeated to repair observation.

The outer imports only the checked3443-byte original guard as its bootstrap source dependency and becomes a subreaper before launch. Workload source/input hashes and synchronous preparation stay inside the service. Outer owns the canonical NONBLOCK host.lock, independently cleans/reaps the launcher PGID using original stop_group even if the leader exited, stops the systemd service, and requires launcher-group-empty plus service-cgroup-empty before writing outer-terminal.json and permitting unlock. A cleanup observation failure retains the lock and retries cleanup/proof; it cannot become permission to unwind. No runtime qualification is claimed for this source.

Successful worker `complete.json` links admission, full raw command/cwd/start/end/exit/stdout/stderr/time, terminal and expected outputs. `outer-terminal.json` separately binds launcher cleanup events and cgroup proof. Consumers must retain both; worker completion alone does not establish the whole-unit boundary. Failed attempts stay immutable. Current tests use a test-only lock and systemd transport stand-ins for direct outer-path controls, alongside real original-guard child processes; those do not establish the canonical lock or actual service caps. Root's real canary does.

## Root-authored request example (not an admission)

This complete keyset is a documentation template. Its expired dates and placeholder pins deliberately fail validation. Root replaces every placeholder, freezes the exact request/digest and assigns a fresh output attempt after independent source review. A lane must not turn this template into its own admission.

```json
{
  "schema": "bounded-command/1",
  "id": "example-not-admission",
  "not_before_utc": "2000-01-01T00:00:00+00:00",
  "expires_utc": "2000-01-01T00:01:00+00:00",
  "root": "/home/jake/Projects/nanopore_basecaller-next-stock-compare",
  "cwd": "/home/jake/Projects/nanopore_basecaller-next-stock-compare",
  "argv": ["/home/jake/.local/bin/uv", "run", "--project", "/home/jake/Projects/nanopore_basecaller-retrieval", "--no-sync", "python", "-m", "unittest", "discover", "-s", "/home/jake/Projects/nanopore_basecaller-next-stock-compare/tests", "-p", "test_stock_feedback.py", "-v"],
  "env": {
    "UV_PROJECT_ENVIRONMENT": "/home/jake/Projects/nanopore_basecaller-retrieval/.venv",
    "UV_OFFLINE": "1",
    "UV_PYTHON_DOWNLOADS": "never",
    "PYTHONDONTWRITEBYTECODE": "1",
    "LC_ALL": "C",
    "HOME": "/home/jake",
    "PATH": "<Root-observed-exact-PATH>",
    "XDG_RUNTIME_DIR": "<Root-observed-runtime-directory>",
    "DBUS_SESSION_BUS_ADDRESS": "<Root-observed-user-bus-address>"
  },
  "source_pins": [{"path": "<Root-pinned-absolute-source-path>", "size": 0, "sha256": "<Root-verified-SHA256>"}],
  "input_pins": [],
  "expected_files": ["/home/jake/Projects/nanopore_basecaller-next-stock-compare/results/stock-feedback/qualification-02/stdout", "/home/jake/Projects/nanopore_basecaller-next-stock-compare/results/stock-feedback/qualification-02/stderr", "/home/jake/Projects/nanopore_basecaller-next-stock-compare/results/stock-feedback/qualification-02/time.txt"],
  "roles": {
    "unit": "F4/engineering",
    "inputs": {},
    "outputs": {
      "test-stdout": "/home/jake/Projects/nanopore_basecaller-next-stock-compare/results/stock-feedback/qualification-02/stdout",
      "test-stderr": "/home/jake/Projects/nanopore_basecaller-next-stock-compare/results/stock-feedback/qualification-02/stderr",
      "test-time": "/home/jake/Projects/nanopore_basecaller-next-stock-compare/results/stock-feedback/qualification-02/time.txt"
    }
  },
  "output_roots": ["/home/jake/Projects/nanopore_basecaller-next-stock-compare/results/stock-feedback"],
  "profile": "engineering",
  "wall_seconds": 300,
  "cpus": 2,
  "memory_bytes": 4294967296,
  "address_space_bytes": 8589934592,
  "swap_bytes": 0,
  "growth_bytes": 104857600,
  "aggregate_bytes": 4294967296,
  "reserve_bytes": 32212254720
}
```

F1 uses the same complete keyset with its own canonical root/cwd/output roots, frozen exact native argv and full dependency/input pins. Concrete role examples are `{"unit":"F1/mapper","inputs":{"query-bam":0,"reference-index":1},"outputs":{"mapped-sam":"<exact-success-file>"}}`, `{"unit":"F1/samtools","inputs":{"mapped-bam":0},"outputs":{"sam":"<exact-success-file>"}}`, and `{"unit":"F1/decoder","inputs":{"tensor":0,"candidate-batch":1},"outputs":{"decision":"<exact-success-file>"}}`. These roles do not prescribe or authorize native commands. Root must copy the exact argv from F1's separately frozen source plan and bind each named input to its corresponding input_pins index. A whole-reference mapper may require the separately admitted mapping16/24GiB profile; changing only the profile label while retaining4/8GiB is rejected.

If TERM interrupts the worker's wait, terminal.json records the actual return code observed after original-guard cleanup and `exit_known:true`. A genuinely unavailable return code stays null with `exit_known:false` and a failed status. If manager KILL prevents worker receipts, outer-terminal.json records failure and the exact missing_worker_records list; missing native clocks/status are not reconstructed and no completion is accepted.
