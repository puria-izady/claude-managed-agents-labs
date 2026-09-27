"""Offline checks for the SDK contracts used in the course notebooks."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx2
from anthropic import Anthropic, DefaultHttpxClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
from session_files import wait_for_session_file  # noqa: E402


class NotebookContractTests(unittest.TestCase):
    def test_code_cells_parse_and_memory_calls_do_not_pass_other_betas(self):
        notebooks = sorted(ROOT.glob("lab_*/lab*.ipynb"))
        self.assertEqual(len(notebooks), 13)
        memory_calls = 0
        for notebook in notebooks:
            data = json.loads(notebook.read_text())
            for index, cell in enumerate(data["cells"]):
                if cell["cell_type"] != "code":
                    continue
                source = "".join(cell["source"])
                tree = ast.parse(source, filename=f"{notebook.name}:cell{index}")
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    call_name = ast.unparse(node.func)
                    if call_name.startswith("client.beta.memory_stores."):
                        memory_calls += 1
                        self.assertNotIn("betas", [kw.arg for kw in node.keywords])
        self.assertGreater(memory_calls, 0)

    def test_lab10_memory_listing_uses_directory_prefix(self):
        notebook = json.loads(
            (ROOT / "lab_10_support_memory" / "lab10.ipynb").read_text()
        )
        source = "".join(notebook["cells"][6]["source"])
        tree = ast.parse(source)
        listings = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "client.beta.memory_stores.memories.list"
        ]
        self.assertEqual(len(listings), 1)
        prefix = next(kw.value for kw in listings[0].keywords if kw.arg == "path_prefix")
        self.assertEqual(ast.literal_eval(prefix), "/")
        self.assertIn("memory.path == path", source)

    def test_sdk_sends_only_memory_beta_header(self):
        seen = []

        def respond(request):
            seen.append((str(request.url), request.headers.get("anthropic-beta")))
            if "/memories" in str(request.url):
                return httpx2.Response(
                    200,
                    json={
                        "id": "mem_123",
                        "type": "memory",
                        "path": "/profile.md",
                        "content": "hello",
                        "created_at": "2026-09-27T00:00:00Z",
                        "updated_at": "2026-09-27T00:00:00Z",
                    },
                )
            return httpx2.Response(
                200,
                json={
                    "id": "memstore_test",
                    "type": "memory_store",
                    "name": "test",
                    "description": "test",
                    "created_at": "2026-09-27T00:00:00Z",
                    "updated_at": "2026-09-27T00:00:00Z",
                    "metadata": {},
                    "archived_at": None,
                },
            )

        client = Anthropic(
            api_key="offline-test",
            http_client=DefaultHttpxClient(transport=httpx2.MockTransport(respond)),
        )
        store = client.beta.memory_stores.create(name="test")
        memory = client.beta.memory_stores.memories.create(
            store.id, path="/profile.md", content="hello"
        )
        self.assertEqual(store.id, "memstore_test")
        self.assertEqual(memory.id, "mem_123")
        self.assertEqual(len(seen), 2)
        for url, header in seen:
            self.assertIn("/v1/memory_stores", url)
            self.assertEqual(header, "agent-memory-2026-07-22")

    def test_delayed_session_output_can_be_downloaded(self):
        output = SimpleNamespace(id="file_123", filename="brief.md")

        class FakeDownload:
            def write_to_file(self, path):
                Path(path).write_text("ready")

        class FakeFiles:
            def __init__(self):
                self.calls = 0
                self.downloaded = []

            def list(self, *, scope_id, betas):
                self.calls += 1
                self_scope.assertEqual(scope_id, "sesn_123")
                self_scope.assertEqual(betas, ["managed-agents-2026-04-01"])
                return [] if self.calls < 3 else [output]

            def download(self, file_id):
                self.downloaded.append(file_id)
                return FakeDownload()

        self_scope = self
        files = FakeFiles()
        client = SimpleNamespace(beta=SimpleNamespace(files=files))
        with patch("session_files.time.sleep") as sleep, tempfile.TemporaryDirectory() as tmp:
            found = wait_for_session_file(
                client, "sesn_123", "brief.md", betas=["managed-agents-2026-04-01"]
            )
            client.beta.files.download(found.id).write_to_file(Path(tmp) / found.filename)
            self.assertEqual((Path(tmp) / "brief.md").read_text(), "ready")
            self.assertEqual(sleep.call_count, 2)
        self.assertEqual(files.calls, 3)
        self.assertEqual(files.downloaded, ["file_123"])

    def test_missing_output_stops_after_five_lists(self):
        files = SimpleNamespace(list=lambda **kwargs: [])
        client = SimpleNamespace(beta=SimpleNamespace(files=files))
        with patch("session_files.time.sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "five file listings"):
                wait_for_session_file(client, "sesn_123", "brief.md", betas=[])
        self.assertEqual(sleep.call_count, 4)


if __name__ == "__main__":
    unittest.main()
