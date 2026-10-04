import io
import os
import json
import shutil
import struct
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from sbo_ingestion.native_host import load_config, process_request, read_frame, write_frame

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def native(tmp_path):
    capture, brain, private = (tmp_path / name for name in ("captures", "brain", "private"))
    for root in (capture, brain, private):
        root.mkdir()
    folder = capture / "chatgpt" / "2026-10-04_native-case"
    folder.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "kura-chatgpt.md", folder / "conversation.md")
    shutil.copyfile(FIXTURES / "capture.json", folder / "capture.json")
    data = {"version": 1, "extension_id": "a" * 32, "capture_root": str(capture),
            "brain_root": str(brain), "private_root": str(private)}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(data), encoding="utf-8")
    config = load_config(config_file, f"chrome-extension://{'a' * 32}/")
    request = {"v": 1, "id": "test-1", "op": "process",
               "path": "chatgpt/2026-10-04_native-case/conversation.md",
               "sha256": sha256((folder / "capture.json").read_bytes()).hexdigest()}
    return config_file, config, request


def test_host_rejects_origin_and_overlapping_roots_before_processing(native):
    path, config, _ = native
    with pytest.raises(ValueError, match="Origin"):
        load_config(path, f"chrome-extension://{'b' * 32}/")
    value = json.loads(path.read_text())
    value["private_root"] = str(config["brain_root"])
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="overlap"):
        load_config(path, f"chrome-extension://{'a' * 32}/")


def test_native_intake_is_repeat_safe_and_never_calls_model(native, monkeypatch):
    _, config, request = native
    monkeypatch.setattr("sbo_ingestion.ingest.summarize", lambda *_args, **_kwargs: pytest.fail("paid call"))
    first = process_request(request, config)
    assert first["ok"] and first["processed"] == 1 and first["paidApiCalls"] == 0
    second = process_request(request, config)
    assert second["ok"] and second["unchanged"] and second["processed"] == 0
    assert len(list(config["brain_root"].rglob("*.md"))) == 1
    reply = json.dumps(first)
    assert "chat-history" not in reply and "private_root" not in reply and "content" not in reply


def test_native_rejects_changed_packet_and_arbitrary_operations(native):
    _, config, request = native
    assert process_request({**request, "sha256": "b" * 64}, config)["code"] == "capture_changed"
    for changes in [{"path": "../secrets/conversation.md"}, {"op": "read_raw"},
                    {"path": "chatgpt/2026-10-04_native-case/conversation.md:secret"},
                    {"mode": "api"}, {"brain_root": "/other"}, {"v": True}]:
        result = process_request({**request, **changes}, config)
        assert result["ok"] is False
        assert set(result) <= {"v", "id", "ok", "code"}
    assert not list(config["private_root"].rglob("*.md"))


def test_native_framing_handles_unicode_and_rejects_incomplete_or_large_frames():
    stream = io.BytesIO()
    write_frame(stream, {"v": 1, "text": "日本語 🙂"})
    stream.seek(0)
    assert read_frame(stream)["text"] == "日本語 🙂"
    assert read_frame(stream) is None
    for body in [b"\x00", struct.pack("=I", 40_000), struct.pack("=I", 5) + b"{}"]:
        with pytest.raises(ValueError):
            read_frame(io.BytesIO(body))


def test_real_python_host_emits_only_framed_metadata(native):
    path, _, request = native
    stream = io.BytesIO()
    write_frame(stream, {"v": 1, "id": "hello", "op": "hello"})
    write_frame(stream, request)
    result = subprocess.run([sys.executable, "-m", "sbo_ingestion.native_host", "--config",
                             str(path), f"chrome-extension://{'a' * 32}/"],
                            input=stream.getvalue(), capture_output=True, timeout=20)
    assert result.returncode == 0 and not result.stderr
    replies = io.BytesIO(result.stdout)
    assert read_frame(replies)["mode"] == "agent"
    assert read_frame(replies)["processed"] == 1
    assert read_frame(replies) is None
    assert len(result.stdout) < 1024


@pytest.mark.skipif(os.name != "nt", reason="Current-user Chrome installer is Windows only")
def test_windows_installer_and_actual_cmd_launcher_are_repeat_safe(native, tmp_path):
    _, config, request = native
    installer = Path(__file__).parents[1] / "scripts" / "install-kura-native.ps1"
    install = tmp_path / "host files Ω (snapshot)"
    command = ["pwsh", "-NoProfile", "-File", str(installer), "-ExtensionId", "a" * 32,
               "-PythonExe", sys.executable, "-InstallRoot", str(install),
               "-CaptureRoot", str(config["capture_root"]), "-BrainRoot", str(config["brain_root"]),
               "-PrivateRoot", str(config["private_root"])]
    for _ in range(2):
        prepared = subprocess.run(command, capture_output=True, timeout=20)
        assert prepared.returncode == 0, prepared.stderr.decode("utf-8", errors="replace")
    manifest = json.loads((install / "ai.frankx.kura_intake.json").read_text(encoding="utf-8"))
    assert manifest["allowed_origins"] == [f"chrome-extension://{'a' * 32}/"]
    assert (install / "lib" / "sbo_ingestion" / "native_host.py").is_file()
    assert " -P -m " in (install / "kura-intake.cmd").read_text(encoding="utf-8")
    stream = io.BytesIO()
    write_frame(stream, request)
    launched = subprocess.run(["cmd.exe", "/d", "/c", manifest["path"],
                               f"chrome-extension://{'a' * 32}/"], input=stream.getvalue(),
                              capture_output=True, timeout=20)
    assert launched.returncode == 0, launched.stderr.decode("utf-8", errors="replace")
    assert read_frame(io.BytesIO(launched.stdout))["processed"] == 1
    retried = subprocess.run(["cmd.exe", "/d", "/c", manifest["path"],
                              f"chrome-extension://{'a' * 32}/"], input=stream.getvalue(),
                             capture_output=True, timeout=20)
    assert retried.returncode == 0
    assert read_frame(io.BytesIO(retried.stdout))["processed"] == 0
    config_file = install / "config.json"
    config_file.write_text("preserve different configuration", encoding="utf-8")
    refused = subprocess.run(command, capture_output=True, timeout=20)
    assert refused.returncode != 0
    assert config_file.read_text(encoding="utf-8") == "preserve different configuration"


def test_new_packet_with_stale_markdown_cannot_be_acknowledged(native):
    _, config, request = native
    packet_path = config["capture_root"] / request["path"]
    packet_path = packet_path.with_name("capture.json")
    value = json.loads(packet_path.read_text(encoding="utf-8"))
    value["renderedBody"] += "\nChanged packet without its Markdown"
    packet_path.write_text(json.dumps(value), encoding="utf-8")
    result = process_request({**request, "sha256": sha256(packet_path.read_bytes()).hexdigest()}, config)
    assert result["ok"] is False and result["code"] == "capture_rejected"
    assert not list(config["brain_root"].rglob("*.md"))


def test_concurrent_real_hosts_create_one_note_and_leave_retry_safe(native):
    path, config, request = native
    stream = io.BytesIO()
    write_frame(stream, request)
    command = [sys.executable, "-m", "sbo_ingestion.native_host", "--config", str(path),
               f"chrome-extension://{'a' * 32}/"]
    processes = [subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE) for _ in range(2)]
    try:
        for process in processes:
            process.stdin.write(stream.getvalue())
            process.stdin.close()
            process.stdin = None
        replies = []
        for process in processes:
            output, error = process.communicate(timeout=20)
            assert process.returncode == 0 and not error
            replies.append(read_frame(io.BytesIO(output)))
        assert sum(reply.get("processed", 0) for reply in replies) == 1
        assert all(reply.get("processed") in (0, 1) or reply.get("code") == "capture_rejected" for reply in replies)
        assert len(list(config["brain_root"].rglob("*.md"))) == 1
        retry = subprocess.run(command, input=stream.getvalue(), capture_output=True, timeout=20)
        assert retry.returncode == 0
        assert read_frame(io.BytesIO(retry.stdout))["processed"] == 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
