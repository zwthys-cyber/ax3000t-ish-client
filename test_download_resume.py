"""Real localhost HTTP transfers: truncation, Range validation and hash gates."""
import contextlib
import hashlib
import http.server
import io
import os
import re
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import release


class DownloadChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = b"0123456789abcdefghijklmnopqrstuvwxyz"
        self.body = self.data
        self.requests = []
        self.mode = "range"
        self.truncate = 0
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                requested = self.headers.get("Range")
                owner.requests.append(requested)
                match = re.fullmatch(r"bytes=(\d+)-(\d+)", requested or "")
                if owner.mode == "ignore" or not match:
                    start, end, status = 0, len(owner.body)-1, 200
                else:
                    start, end = map(int, match.groups())
                    status = 206
                data = owner.body[start:end+1]
                self.send_response(status)
                if status == 206:
                    reported_start = 0 if owner.mode == "wrong-start" else start
                    total = len(owner.body) + (1 if owner.mode == "wrong-total" else 0)
                    self.send_header("Content-Range", f"bytes {reported_start}-{end}/{total}")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if owner.mode == "empty":
                    data = b""
                elif owner.truncate:
                    owner.truncate -= 1
                    data = data[:3]
                self.wfile.write(data)
                self.close_connection = True

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.rel = SimpleNamespace(tag="v-test", assets={"image.bin": {
            "url": f"http://127.0.0.1:{self.server.server_port}/image.bin",
            "size": len(self.data), "digest": "sha256:"+hashlib.sha256(self.data).hexdigest()}})
        self.final = os.path.join(self.tmp.name, "image.bin")
        self.part = self.final + ".part"
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(release, "DOWNLOAD_BLOCK_SIZE", 8))
        self.stack.enter_context(patch.object(release.time, "sleep"))
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def prefix(self, data):
        with open(self.part, "wb") as output:
            output.write(data)

    def fetch(self, **kwargs):
        return release.download(self.rel, "image.bin", self.tmp.name, progress=False, **kwargs)

    def assert_complete(self):
        with open(self.final, "rb") as source:
            self.assertEqual(source.read(), self.data)
        self.assertFalse(os.path.exists(self.part))

    def test_short_response_resumes_at_actual_written_offset(self):
        self.truncate = 1
        self.fetch()
        self.assertEqual(self.requests[:2], ["bytes=0-7", "bytes=3-10"])
        self.assert_complete()

    def test_restart_reuses_partial_file(self):
        self.prefix(self.data[:11])
        self.fetch()
        self.assertEqual(self.requests[0], "bytes=11-18")
        self.assert_complete()

    def test_full_response_replaces_partial_instead_of_appending(self):
        self.prefix(self.data[:11])
        self.mode = "ignore"
        self.fetch()
        self.assertEqual(len(self.requests), 1)
        self.assert_complete()

    def test_wrong_content_range_never_appends_or_promotes(self):
        for mode in ("wrong-start", "wrong-total"):
            with self.subTest(mode=mode):
                self.prefix(self.data[:11])
                self.mode = mode
                with self.assertRaises(release.ReleaseError):
                    self.fetch()
                with open(self.part, "rb") as source:
                    self.assertEqual(source.read(), self.data[:11])
                self.assertFalse(os.path.exists(self.final))

    def test_bad_digest_is_removed_and_not_promoted(self):
        self.body = b"x" * len(self.data)
        with self.assertRaises(release.ReleaseError):
            self.fetch()
        self.assertFalse(os.path.exists(self.final))
        self.assertFalse(os.path.exists(self.part))

    def test_exhausted_retries_retain_partial_and_next_run_resumes(self):
        self.prefix(self.data[:11])
        self.mode = "empty"
        with self.assertRaises(release.ReleaseError):
            self.fetch(retries=1)
        self.assertEqual(len(self.requests), 2)
        self.assertFalse(os.path.exists(self.final))
        with open(self.part, "rb") as source:
            self.assertEqual(source.read(), self.data[:11])
        self.mode = "range"
        self.fetch()
        self.assertEqual(self.requests[2], "bytes=11-18")
        self.assert_complete()

    def test_complete_partial_requires_digest_before_promotion(self):
        self.prefix(b"x"*len(self.data))
        with self.assertRaises(release.ReleaseError):
            self.fetch()
        self.assertEqual(self.requests, [])
        self.assertFalse(os.path.exists(self.final))
        self.prefix(self.data)
        self.fetch()
        self.assertEqual(self.requests, [])
        self.assert_complete()

    def test_manifest_and_api_digests_cannot_disagree(self):
        with self.assertRaises(release.ReleaseError):
            self.fetch(expected_sha256="0"*64)
        self.assertEqual(self.requests, [])

    def test_cached_final_still_requires_trusted_digest(self):
        with open(self.final, "wb") as output:
            output.write(b"x"*len(self.data))
        self.fetch()
        self.assertTrue(self.requests)
        self.assert_complete()


if __name__ == "__main__":
    unittest.main()
