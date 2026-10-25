import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for directory in ("scripts", "config", "logs", "work"):
            (self.root / directory).mkdir()
        for name in ("fetch.py", "record-command.sh"):
            shutil.copy2(PROJECT_ROOT / "scripts" / name, self.root / "scripts" / name)
        self.payload = bytes(range(256)) * 8
        self.served_payload = self.payload
        self.range_total = len(self.payload)
        self.requests = []
        fixture = self

        class RangeHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                fixture.requests.append(dict(self.headers))
                match = re.fullmatch(r"bytes=(\d+)-(\d+)", self.headers.get("Range", ""))
                if self.path != "/asset.bin" or match is None:
                    self.send_error(400)
                    return
                start, end = map(int, match.groups())
                if not 0 <= start <= end < len(fixture.served_payload):
                    self.send_error(416)
                    return
                body = fixture.served_payload[start:end + 1]
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{fixture.range_total}")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
        self.server_thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.01), daemon=True
        )
        self.server_thread.start()
        self.addCleanup(self.stop_server)
        self.asset = {
            "id": "fixture",
            "path": "inputs/asset.bin",
            "url": f"http://127.0.0.1:{self.server.server_port}/asset.bin",
            "bytes": len(self.payload),
            "etag": "fixture-version",
            "md5": hashlib.md5(self.payload).hexdigest(),
            "sha256": hashlib.sha256(self.payload).hexdigest(),
        }
        self.target = self.root / self.asset["path"]

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=5)

    def run_command(self, command, cwd=None):
        environment = os.environ.copy()
        environment["NO_PROXY"] = environment["no_proxy"] = "127.0.0.1,localhost"
        return subprocess.run(
            command, cwd=cwd or self.root, env=environment,
            capture_output=True, text=True, timeout=20,
        )

    def fetch(self):
        (self.root / "config/assets.json").write_text(json.dumps([self.asset]))
        return self.run_command([sys.executable, str(self.root / "scripts/fetch.py"), "fixture"])

    def test_fetch_acquires_exact_bytes_and_reports_hashes(self):
        result = self.fetch()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), self.payload)
        receipt = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(receipt, {
            "id": "fixture", "bytes": len(self.payload),
            "md5": self.asset["md5"], "sha256": self.asset["sha256"],
        })
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0]["Range"], f"bytes=0-{len(self.payload) - 1}")
        self.assertEqual(self.requests[0]["If-Match"], '"fixture-version"')
        self.assertFalse(self.target.with_name("asset.bin.parts").exists())

        repeated = self.fetch()

        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(json.loads(repeated.stdout.splitlines()[-1]), receipt)
        self.assertEqual(len(self.requests), 1)

    def test_fetch_rejects_upstream_md5_corruption(self):
        del self.asset["sha256"]
        self.served_payload = bytes([self.payload[0] ^ 1]) + self.payload[1:]

        result = self.fetch()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("md5 mismatch", result.stderr.lower())
        self.assertEqual(len(self.requests), 1)
        self.assertFalse(self.target.exists())
        self.assertFalse(any(line.startswith('{"id":') for line in result.stdout.splitlines()))

    def test_fetch_resumes_a_verified_partial_range(self):
        parts = self.target.with_name("asset.bin.parts")
        parts.mkdir(parents=True)
        (parts / "0.partial").write_bytes(self.payload[:512])
        (parts / "0.headers").write_text(
            f"HTTP/1.1 206 Partial Content\nContent-Range: bytes 0-{len(self.payload)-1}/{len(self.payload)}\n"
        )

        result = self.fetch()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), self.payload)
        self.assertEqual(self.requests[0]["Range"], f"bytes=512-{len(self.payload)-1}")

    def test_fetch_preserves_a_received_prefix_after_a_connection_reset(self):
        parts = self.target.with_name("asset.bin.parts")
        parts.mkdir(parents=True)
        (parts / "0.partial").write_bytes(self.payload[:512])
        (parts / "0.headers").write_text(
            f"HTTP/1.1 206 Partial Content\nContent-Range: bytes 0-{len(self.payload)-1}/{len(self.payload)}\n"
        )
        (parts / "0.remainder").write_bytes(self.payload[512:1024])
        (parts / "0.remainder-headers").write_text(
            f"HTTP/1.1 206 Partial Content\nContent-Range: bytes 512-{len(self.payload)-1}/{len(self.payload)}\n"
        )

        result = self.fetch()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), self.payload)
        self.assertEqual(self.requests[0]["Range"], f"bytes=1024-{len(self.payload)-1}")

    def test_fetch_rejects_a_partial_from_a_failed_final_http_response(self):
        parts = self.target.with_name("asset.bin.parts")
        parts.mkdir(parents=True)
        (parts / "0.partial").write_bytes(self.payload[:512])
        (parts / "0.headers").write_text(
            f"HTTP/1.1 206 Partial Content\nContent-Range: bytes 0-{len(self.payload)-1}/{len(self.payload)}\n\n"
            "HTTP/1.1 500 Internal Server Error\nContent-Length: 512\n"
        )

        result = self.fetch()

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.requests, [])

    def test_fetch_resumes_after_atomic_merge_before_remainder_cleanup(self):
        parts = self.target.with_name("asset.bin.parts")
        parts.mkdir(parents=True)
        (parts / "0.partial").write_bytes(self.payload[:1024])
        (parts / "0.headers").write_text(
            f"HTTP/1.1 206 Partial Content\nContent-Range: bytes 0-{len(self.payload)-1}/{len(self.payload)}\n"
        )
        (parts / "0.remainder").write_bytes(self.payload[512:1024])
        (parts / "0.remainder-headers").write_text(
            f"HTTP/1.1 206 Partial Content\nContent-Range: bytes 512-{len(self.payload)-1}/{len(self.payload)}\n"
        )

        result = self.fetch()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), self.payload)
        self.assertEqual(self.requests[0]["Range"], f"bytes=1024-{len(self.payload)-1}")

    def test_fetch_rejects_inconsistent_already_merged_remainder(self):
        parts = self.target.with_name("asset.bin.parts")
        parts.mkdir(parents=True)
        (parts / "0.partial").write_bytes(self.payload[:1024])
        (parts / "0.headers").write_text(
            f"HTTP/1.1 206 Partial Content\nContent-Range: bytes 0-{len(self.payload)-1}/{len(self.payload)}\n"
        )
        (parts / "0.remainder").write_bytes(b"x" * 512)
        (parts / "0.remainder-headers").write_text(
            f"HTTP/1.1 206 Partial Content\nContent-Range: bytes 512-{len(self.payload)-1}/{len(self.payload)}\n"
        )

        result = self.fetch()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Interrupted merge contains inconsistent bytes", result.stderr)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.requests, [])

    def test_fetch_rejects_incorrect_content_range_total(self):
        self.range_total = len(self.payload) * 10

        result = self.fetch()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("range", result.stderr.lower())
        self.assertFalse(self.target.exists())
        self.assertEqual(len(self.requests), 1)

    def test_fetch_rejects_existing_wrong_size_without_downloading(self):
        self.target.parent.mkdir()
        self.target.write_bytes(b"incomplete existing input")

        result = self.fetch()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("wrong size", result.stderr.lower())
        self.assertEqual(self.target.read_bytes(), b"incomplete existing input")
        self.assertEqual(self.requests, [])

    def assert_recorded_command(self, exit_status):
        arguments = ["a space", "single'quote", 'double"quote', "$HOME; echo unexpected", r"back\slash"]
        program = (
            "import json, os, sys; "
            "print(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd()})); "
            "print('captured stderr', file=sys.stderr); "
            f"sys.exit({exit_status})"
        )
        command = [sys.executable, "-c", program, *arguments]
        result = self.run_command(
            ["bash", str(self.root / "scripts/record-command.sh"), "fixture", *command],
            cwd=self.root / "work",
        )

        self.assertEqual(result.returncode, exit_status, result.stderr)
        self.assertEqual(result.stderr, "")
        run = Path(result.stdout.strip())
        self.assertEqual(run.parent, self.root / "logs")
        self.assertEqual(list((self.root / "logs").iterdir()), [run])
        self.assertEqual(shlex.split((run / "command.sh").read_text()), command)
        self.assertEqual((run / "cwd.txt").read_text().strip(), str(self.root / "work"))
        self.assertEqual(json.loads((run / "stdout").read_text()), {
            "argv": arguments, "cwd": str(self.root / "work"),
        })
        self.assertEqual((run / "stderr").read_text(), "captured stderr\n")
        self.assertEqual((run / "exit-status.txt").read_text(), f"{exit_status}\n")
        start = datetime.fromisoformat((run / "start.txt").read_text().strip())
        end = datetime.fromisoformat((run / "end.txt").read_text().strip())
        self.assertIsNotNone(start.tzinfo)
        self.assertIsNotNone(end.tzinfo)
        self.assertLessEqual(start, end)
        self.assertIn(f"Exit status: {exit_status}", (run / "time.txt").read_text())

    def test_recorder_captures_success(self):
        self.assert_recorded_command(0)

    def test_recorder_captures_failure_and_propagates_exit_status(self):
        self.assert_recorded_command(7)


if __name__ == "__main__":
    unittest.main()
