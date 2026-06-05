import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_ingress_detects_warm_node_from_registry(tmp_path):
    ingress = _load_module("hermes_ingress", ROOT / "services" / "hermes_ingress.py")
    nodes_path = tmp_path / "nodes.json"
    nodes_path.write_text(json.dumps({
        "nodes": {
            "context-owner": {"profile": "context-owner", "mode": "warm_node"},
            "sales": {"profile": "sales", "mode": "live_gateway"},
        }
    }), encoding="utf-8")

    assert ingress.node_config("context-owner", nodes_path)["mode"] == "warm_node"
    assert ingress.node_config("missing", nodes_path) is None


def test_node_host_loads_only_warm_nodes(tmp_path):
    node_host_mod = _load_module("hermes_node_host", ROOT / "services" / "hermes_node_host.py")
    nodes_path = tmp_path / "nodes.json"
    nodes_path.write_text(json.dumps({
        "nodes": {
            "context-owner": {"profile": "context-owner", "mode": "warm_node"},
            "sales": {"profile": "sales", "mode": "live_gateway"},
        }
    }), encoding="utf-8")

    host = node_host_mod.NodeHost(
        nodes_path=nodes_path,
        hermes_root=tmp_path / "profiles",
        ingress_url="http://127.0.0.1:7135/v1/messages",
        hermes_agent_root=tmp_path / "hermes-agent",
    )

    assert sorted(host.nodes()) == ["context-owner"]


def test_node_prompt_preserves_sender_subject_and_body():
    node_host_mod = _load_module("hermes_node_host_prompt", ROOT / "services" / "hermes_node_host.py")
    prompt = node_host_mod.node_prompt({
        "from": "aura:aura-route:router",
        "subject": "Context question",
        "body": "What owns this folder?",
        "metadata": {"request_id": "req-1"},
    }, "context-owner")

    assert "context-owner" in prompt
    assert "aura:aura-route:router" in prompt
    assert "Context question" in prompt
    assert "req-1" in prompt
    assert "What owns this folder?" in prompt


def test_node_prompt_injects_territory_config():
    node_host_mod = _load_module("hermes_node_host_territory_prompt", ROOT / "services" / "hermes_node_host.py")
    prompt = node_host_mod.node_prompt({
        "from": "service:discord-damian",
        "subject": "Context question",
        "body": "What changed?",
    }, "aura-context-owner", {
        "territory": {
            "context_name": "aura",
            "visible_name": "aura-context-owner",
            "context_root": "/home/axp/projects/aura/context",
            "project_root": "/home/axp/projects/aura",
            "flex_cell": "aura-context",
            "source_order": ["current", "changes", "plans"],
        }
    })

    assert "Node territory:" in prompt
    assert "context_name: aura" in prompt
    assert "context_root: /home/axp/projects/aura/context" in prompt
    assert "source_order: current, changes, plans" in prompt


def test_warm_node_turn_runs_under_profile_home(monkeypatch, tmp_path):
    node_host_mod = _load_module("hermes_node_host_profile_home", ROOT / "services" / "hermes_node_host.py")
    profile_root = tmp_path / "profiles" / "assistant"
    profile_root.mkdir(parents=True)
    observed = []

    class Agent:
        def run_conversation(self, prompt, conversation_history=None):
            observed.append(("run", prompt, conversation_history))
            return {"messages": [{"role": "assistant", "content": "ok"}], "final_response": "ok"}

    monkeypatch.setattr(node_host_mod.WarmNode, "_ensure_agent", lambda self: Agent())

    def fake_set(path):
        observed.append(("set", path))
        return "token"

    def fake_reset(token):
        observed.append(("reset", token))

    class Constants:
        set_hermes_home_override = staticmethod(fake_set)
        reset_hermes_home_override = staticmethod(fake_reset)

    monkeypatch.setitem(sys.modules, "hermes_constants", Constants)

    node = node_host_mod.WarmNode(
        name="assistant",
        config={"profile": "assistant"},
        hermes_root=tmp_path / "profiles",
        ingress_url="http://127.0.0.1:7135/v1/messages",
        hermes_agent_root=tmp_path / "hermes-agent",
    )

    result = node.handle({"from": "test", "subject": "hello", "body": "body"})

    assert result["response"] == "ok"
    assert observed[0] == ("set", profile_root)
    assert observed[-1] == ("reset", "token")


def test_ingress_waits_for_warm_node_answers(monkeypatch):
    ingress = _load_module("hermes_ingress_timeout", ROOT / "services" / "hermes_ingress.py")
    observed = {}

    class Response:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"ok": True, "response": "ready"}).encode("utf-8")

    def fake_urlopen(req, timeout=None):
        observed["timeout"] = timeout
        return Response()

    monkeypatch.setattr(ingress.urlrequest, "urlopen", fake_urlopen)

    result = ingress.dispatch_hermes_node_host(
        "context-owner",
        {
            "target": "hermes:context-owner",
            "body": "hello",
            "delivery": "live",
            "reply_mode": "native",
        },
        "http://127.0.0.1:7136/v1/messages",
    )

    assert result["ok"] is True
    assert observed["timeout"] == 180
