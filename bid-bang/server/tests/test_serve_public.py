"""tools/serve_public.py : serveur local + tunnel + config.json. Aucun tunnel réel n'est ouvert : un faux
`cloudflared` imite la sortie du vrai ; le serveur FastAPI, lui, est démarré pour de bon."""
import importlib.util
import json
import socket
import stat
import subprocess
import urllib.request
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "serve_public.py"
spec = importlib.util.spec_from_file_location("serve_public", SCRIPT)
sp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp)

VERCEL = "https://bidbang.vercel.app"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_extract_tunnel_url_from_cloudflared_logs():
    lines = ["2026-11-12T10:00:00Z INF Requesting new quick Tunnel on trycloudflare.com...",
             "2026-11-12T10:00:02Z INF |  https://quiet-river-1234.trycloudflare.com                       |",
             "2026-11-12T10:00:02Z INF Registered tunnel connection"]
    assert [sp.extract_tunnel_url(l) for l in lines] == [None, "https://quiet-river-1234.trycloudflare.com", None]
    assert sp.extract_tunnel_url("https://evil.example/trycloudflare.com") is None
    assert sp.extract_tunnel_url("http://x.trycloudflare.com") is None


@pytest.mark.parametrize("bad", ["http://x.example", "https://x.example/path", "ftp://x", "", "x.example",
                                 "https://x.example?a=1", "https://127.0.0.1 evil"])
def test_check_https_url_rejects_bad_addresses(bad):
    with pytest.raises(SystemExit):
        sp.check_https_url(bad)


def test_check_https_url_normalises():
    assert sp.check_https_url(" https://a-b.up.railway.app/ ") == "https://a-b.up.railway.app"


def test_write_config_is_valid_json_and_idempotent(tmp_path):
    cfg = tmp_path / "web_build" / "config.json"
    assert sp.write_config(cfg, "https://one.trycloudflare.com") is True
    assert json.loads(cfg.read_text()) == {"server_url": "https://one.trycloudflare.com"}
    assert sp.write_config(cfg, "https://one.trycloudflare.com") is False
    assert sp.write_config(cfg, "https://two.trycloudflare.com") is True
    with pytest.raises(SystemExit):
        sp.write_config(cfg, "http://127.0.0.1:8000")  # jamais d'adresse locale ni en clair
    assert json.loads(cfg.read_text())["server_url"] == "https://two.trycloudflare.com"


def test_server_starts_in_production_mode_for_the_vercel_origin(monkeypatch):
    monkeypatch.setenv("BIDBANG_MOCK_AI", "1")            # ne doit pas fuiter vers le serveur public
    monkeypatch.setenv("BIDBANG_ALLOW_ENV_KEY", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-SECRET-0123456789")
    port = free_port()
    proc = sp.start_server(port, VERCEL)
    try:
        assert sp.wait_http(f"http://127.0.0.1:{port}/health", 30)
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Origin": VERCEL})
        assert urllib.request.urlopen(req).headers["Access-Control-Allow-Origin"] == VERCEL
        other = urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Origin": "https://evil.example"})
        assert urllib.request.urlopen(other).headers.get("Access-Control-Allow-Origin") is None
        local = urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Origin": "http://localhost:8080"})
        assert urllib.request.urlopen(local).headers.get("Access-Control-Allow-Origin") is None  # production
        providers = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/ai/providers").read())
        assert "mock" not in [p["id"] for p in providers["providers"]]
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/docs")
        assert exc.value.code == 404
    finally:
        sp.stop(proc)
    assert proc.poll() is not None


def fake_cloudflared(tmp_path: Path, body: str) -> str:
    path = tmp_path / "cloudflared"
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_start_tunnel_reads_the_address_from_the_logs(tmp_path):
    binary = fake_cloudflared(tmp_path, 'echo "INF Requesting new quick Tunnel"\n'
                                         'echo "INF |  https://calm-fox-42.trycloudflare.com  |"\nsleep 30')
    proc, url = sp.start_tunnel(8000, binary, seconds=10)
    try:
        assert url == "https://calm-fox-42.trycloudflare.com" and proc.poll() is None
    finally:
        sp.stop(proc)
    assert proc.poll() is not None


def test_start_tunnel_fails_clearly_without_an_address(tmp_path):
    binary = fake_cloudflared(tmp_path, 'echo "ERR cannot reach the network"')
    with pytest.raises(SystemExit, match="n'a pas donné d'adresse"):
        sp.start_tunnel(8000, binary, seconds=5)


def test_publish_config_commits_only_config_json_and_pushes(tmp_path):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for k, v in (("user.email", "t@example.com"), ("user.name", "T")):
        subprocess.run(["git", "-C", str(repo), "config", k, v], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote)], check=True)
    (repo / "web_build").mkdir()
    cfg = repo / "web_build" / "config.json"
    (repo / "notes.txt").write_text("v1")
    sp.write_config(cfg, "https://old.trycloudflare.com")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "-u", "origin", "main"], check=True)
    # un travail en cours, sans rapport, ne doit pas être publié
    (repo / "notes.txt").write_text("v2 non terminé")
    subprocess.run(["git", "-C", str(repo), "add", "notes.txt"], check=True)
    sp.write_config(cfg, "https://new.trycloudflare.com")
    msg = sp.publish_config(repo, cfg)
    assert "poussé" in msg
    changed = subprocess.run(["git", "-C", str(repo), "show", "--name-only", "--format=", "HEAD"],
                             capture_output=True, text=True).stdout.split()
    assert changed == ["web_build/config.json"]
    staged = subprocess.run(["git", "-C", str(repo), "diff", "--cached", "--name-only"],
                            capture_output=True, text=True).stdout.split()
    assert staged == ["notes.txt"]                                    # reste en attente, non commité
    remote_cfg = subprocess.run(["git", "-C", str(remote), "show", "main:web_build/config.json"],
                                capture_output=True, text=True).stdout
    assert json.loads(remote_cfg)["server_url"] == "https://new.trycloudflare.com"
    assert "déjà à jour" in sp.publish_config(repo, cfg)               # 2e appel : rien à pousser


def test_main_requires_the_origin_and_cloudflared(capsys, monkeypatch, tmp_path):
    with pytest.raises(SystemExit):
        sp.main(["--cloudflared", str(tmp_path / "absent")])            # --origin manquant
    monkeypatch.delenv("BIDBANG_WEB_ORIGIN", raising=False)
    with pytest.raises(SystemExit):
        sp.main(["--origin", "http://bidbang.vercel.app"])              # pas en https
    assert sp.main(["--origin", VERCEL, "--cloudflared", str(tmp_path / "absent")]) == 1
    err = capsys.readouterr().err
    assert "introuvable" in err and "releases/latest/download/cloudflared-linux-amd64" in err
