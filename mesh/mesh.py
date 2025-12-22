#!/usr/bin/env python3
"""
mesh - Agent communication mesh for Claude Code instances.

Central coordinator that enables real-time agent-to-agent communication:
- Discovery: who exists, where are they
- Routing: @name → socket
- Delivery: queue messages for agents
- Presence: idle/busy status
- Conversations: tracked, bounded exchanges

Usage:
    mesh.py                    # Start mesh daemon
    mesh.py --socket /tmp/mesh.sock  # Custom socket
"""

import os
import sys
import json
import socket
import select
import threading
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

# === CONFIG ===
MESH_SOCKET = Path("/tmp/aura/mesh.sock")
MESH_DIR = Path("/tmp/aura")


@dataclass
class Agent:
    """Registered agent."""
    name: str
    session_id: str
    socket_path: str
    registered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "idle"  # idle, busy, waiting
    last_seen: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Message:
    """Message in transit."""
    id: str
    from_agent: str
    to_agent: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    conversation_id: Optional[str] = None
    delivered: bool = False


@dataclass
class Conversation:
    """Tracked conversation between agents."""
    id: str
    participants: list[str]
    topic: str
    max_turns: int
    current_turn: int = 0
    messages: list[str] = field(default_factory=list)  # message IDs
    status: str = "active"  # active, complete, timeout


class Mesh:
    """Central mesh coordinator."""

    def __init__(self, socket_path: str = None):
        self.socket_path = socket_path or str(MESH_SOCKET)
        self.agents: dict[str, Agent] = {}  # name → Agent
        self.messages: dict[str, Message] = {}  # id → Message
        self.queues: dict[str, list[str]] = {}  # agent_name → [message_ids]
        self.conversations: dict[str, Conversation] = {}  # id → Conversation
        self.server_socket = None
        self.running = False
        self._msg_counter = 0

    def _gen_id(self, prefix: str = "msg") -> str:
        self._msg_counter += 1
        return f"{prefix}-{self._msg_counter}-{datetime.now().strftime('%H%M%S')}"

    # === AGENT MANAGEMENT ===

    def register(self, name: str, session_id: str, socket_path: str) -> dict:
        """Register an agent with the mesh."""
        agent = Agent(
            name=name,
            session_id=session_id,
            socket_path=socket_path
        )
        self.agents[name] = agent
        self.queues[name] = []
        self._log(f"registered: {name} ({session_id[:8]})")
        return {"ok": True, "action": "register", "name": name}

    def unregister(self, name: str) -> dict:
        """Unregister an agent."""
        if name in self.agents:
            del self.agents[name]
            if name in self.queues:
                del self.queues[name]
            self._log(f"unregistered: {name}")
            return {"ok": True, "action": "unregister", "name": name}
        return {"error": f"agent not found: {name}"}

    def heartbeat(self, name: str, status: str = "idle") -> dict:
        """Update agent status."""
        if name in self.agents:
            self.agents[name].last_seen = datetime.now().isoformat()
            self.agents[name].status = status
            return {"ok": True, "action": "heartbeat"}
        return {"error": f"agent not found: {name}"}

    def discover(self) -> dict:
        """List all registered agents."""
        return {
            "ok": True,
            "action": "discover",
            "agents": [asdict(a) for a in self.agents.values()]
        }

    # === MESSAGING ===

    def send(self, from_agent: str, to_agent: str, content: str,
             conversation_id: str = None) -> dict:
        """Send message from one agent to another."""
        if to_agent not in self.agents and to_agent != "all":
            return {"error": f"agent not found: {to_agent}"}

        msg_id = self._gen_id("msg")
        msg = Message(
            id=msg_id,
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            conversation_id=conversation_id
        )
        self.messages[msg_id] = msg

        # Route to recipient(s)
        if to_agent == "all":
            # Broadcast
            for name in self.agents:
                if name != from_agent:
                    self.queues.setdefault(name, []).append(msg_id)
            self._log(f"broadcast from {from_agent}: {content[:50]}...")
        else:
            self.queues.setdefault(to_agent, []).append(msg_id)
            self._log(f"message {from_agent} → {to_agent}: {content[:50]}...")

        # Update conversation if part of one
        if conversation_id and conversation_id in self.conversations:
            conv = self.conversations[conversation_id]
            conv.messages.append(msg_id)
            conv.current_turn += 1
            if conv.current_turn >= conv.max_turns:
                conv.status = "complete"

        return {"ok": True, "action": "send", "message_id": msg_id}

    def receive(self, agent_name: str) -> dict:
        """Get pending messages for an agent."""
        if agent_name not in self.queues:
            return {"ok": True, "action": "receive", "messages": []}

        msg_ids = self.queues[agent_name]
        messages = []
        for msg_id in msg_ids:
            if msg_id in self.messages:
                msg = self.messages[msg_id]
                msg.delivered = True
                messages.append(asdict(msg))

        self.queues[agent_name] = []  # Clear queue
        return {"ok": True, "action": "receive", "messages": messages}

    # === CONVERSATIONS ===

    def start_conversation(self, initiator: str, target: str,
                          topic: str, max_turns: int = 5) -> dict:
        """Start a tracked conversation."""
        conv_id = self._gen_id("conv")
        conv = Conversation(
            id=conv_id,
            participants=[initiator, target],
            topic=topic,
            max_turns=max_turns
        )
        self.conversations[conv_id] = conv
        self._log(f"conversation started: {initiator} ↔ {target} ({topic})")
        return {
            "ok": True,
            "action": "start_conversation",
            "conversation_id": conv_id
        }

    def get_conversation(self, conv_id: str) -> dict:
        """Get conversation status and messages."""
        if conv_id not in self.conversations:
            return {"error": f"conversation not found: {conv_id}"}

        conv = self.conversations[conv_id]
        messages = [asdict(self.messages[mid]) for mid in conv.messages if mid in self.messages]
        return {
            "ok": True,
            "action": "get_conversation",
            "conversation": asdict(conv),
            "messages": messages
        }

    # === SERVER ===

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"\033[35m[mesh {ts}]\033[0m {msg}")

    def handle_request(self, data: str) -> str:
        """Handle incoming request."""
        try:
            req = json.loads(data)
        except json.JSONDecodeError:
            return json.dumps({"error": "invalid json"})

        action = req.get("action", "")

        handlers = {
            "register": lambda: self.register(
                req.get("name"), req.get("session_id"), req.get("socket_path")
            ),
            "unregister": lambda: self.unregister(req.get("name")),
            "heartbeat": lambda: self.heartbeat(req.get("name"), req.get("status", "idle")),
            "discover": lambda: self.discover(),
            "send": lambda: self.send(
                req.get("from"), req.get("to"), req.get("content"),
                req.get("conversation_id")
            ),
            "receive": lambda: self.receive(req.get("name")),
            "start_conversation": lambda: self.start_conversation(
                req.get("initiator"), req.get("target"),
                req.get("topic"), req.get("max_turns", 5)
            ),
            "get_conversation": lambda: self.get_conversation(req.get("conversation_id")),
        }

        if action in handlers:
            return json.dumps(handlers[action]())
        else:
            return json.dumps({"error": f"unknown action: {action}"})

    def start(self):
        """Start the mesh daemon."""
        MESH_DIR.mkdir(exist_ok=True)

        # Clean up old socket
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        self.server_socket.listen(10)
        self.running = True

        self._log(f"started on {self.socket_path}")
        self._log("waiting for agents...")

        try:
            while self.running:
                readable, _, _ = select.select([self.server_socket], [], [], 1.0)

                for sock in readable:
                    conn, _ = self.server_socket.accept()
                    try:
                        data = conn.recv(8192).decode('utf-8')
                        if data:
                            response = self.handle_request(data)
                            conn.send(response.encode('utf-8'))
                    finally:
                        conn.close()

        except KeyboardInterrupt:
            self._log("shutting down...")
        finally:
            self.server_socket.close()
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="mesh - Agent communication coordinator")
    parser.add_argument("--socket", "-s", default=str(MESH_SOCKET), help="Socket path")
    args = parser.parse_args()

    mesh = Mesh(args.socket)
    mesh.start()


if __name__ == "__main__":
    main()
