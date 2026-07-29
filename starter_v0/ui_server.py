from __future__ import annotations

import argparse
import json
import mimetypes
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from chat import (
    ARTIFACTS_DIR,
    ROOT,
    now_iso,
    run_model_tool_loop,
    safe_slug,
    trim_history,
    write_transcript,
)
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


UI_DIR = ROOT / "ui"
TRANSCRIPTS_DIR = ROOT / "transcripts"


def make_transcript_id(version: str, provider: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    return "_".join([safe_slug(version), safe_slug(provider), timestamp])


class AgentSession:
    def __init__(
        self,
        *,
        provider_name: str,
        model: str | None,
        version: str,
        history_window: int,
        max_tool_rounds: int,
        system_prompt_path: Path,
        tools_path: Path,
    ) -> None:
        self.provider_name = provider_name
        self.model = model
        self.version = version
        self.history_window = history_window
        self.max_tool_rounds = max_tool_rounds
        self.system_prompt_path = system_prompt_path
        self.tools_path = tools_path
        self.provider = make_provider(provider_name)
        self.tools = to_openai_tools(load_tool_declarations(tools_path))
        self.system_prompt = system_prompt_path.read_text(encoding="utf-8")
        self.history: list[dict[str, str]] = []
        self.turn_index = 0
        self.transcript_path: Path
        self.transcript: dict[str, Any]
        self.reset_transcript()

    def reset_transcript(self) -> None:
        selected_model = self.model or getattr(self.provider, "default_model", None)
        artifact_version = build_artifact_version(self.version, self.system_prompt_path, self.tools_path)
        transcript_id = make_transcript_id(self.version, self.provider_name)
        self.transcript_path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
        self.transcript = {
            "transcript_id": transcript_id,
            **artifact_version_dict(artifact_version),
            "provider": self.provider_name,
            "model": selected_model,
            "system_prompt": str(self.system_prompt_path),
            "tools": str(self.tools_path),
            "history_window": self.history_window,
            "max_tool_rounds": self.max_tool_rounds,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "turns": [],
        }
        self.history = []
        self.turn_index = 0
        write_transcript(self.transcript_path, self.transcript)

    def metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "model": self.transcript.get("model"),
            "version": self.version,
            "artifact_version": self.transcript.get("artifact_version"),
            "transcript_path": str(self.transcript_path),
            "turn_count": len(self.transcript.get("turns", [])),
        }

    def run_turn(self, user_text: str) -> dict[str, Any]:
        self.turn_index += 1
        messages = [
            {"role": "system", "content": self.system_prompt},
            *trim_history(self.history, self.history_window),
            {"role": "user", "content": user_text},
        ]
        turn_record: dict[str, Any] = {
            "turn_index": self.turn_index,
            "started_at": now_iso(),
            "user": user_text,
            "status": "started",
            "assistant_text": None,
            "rounds": [],
            "tool_events": [],
        }

        try:
            result = run_model_tool_loop(
                provider=self.provider,
                messages=messages,
                tools=self.tools,
                model=self.model,
                max_tool_rounds=self.max_tool_rounds,
            )
            turn_record.update(result)
            assistant_text = result["assistant_text"]
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": assistant_text})
        except Exception as exc:
            turn_record.update({
                "status": "provider_error",
                "error": f"{type(exc).__name__}: {str(exc)}",
            })

        turn_record["ended_at"] = now_iso()
        self.transcript["turns"].append(turn_record)
        write_transcript(self.transcript_path, self.transcript)
        return {"turn": turn_record, "metadata": self.metadata()}


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def safe_static_path(url_path: str) -> Path | None:
    route = unquote(url_path.split("?", 1)[0])
    if route in {"", "/"}:
        route = "/index.html"
    relative = route.lstrip("/")
    candidate = (UI_DIR / relative).resolve()
    ui_root = UI_DIR.resolve()
    if candidate == ui_root or ui_root not in candidate.parents:
        return None
    return candidate


def make_handler(session: AgentSession) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            print(f"{self.address_string()} - {format % args}")

        def do_GET(self) -> None:
            if self.path.startswith("/api/metadata"):
                json_response(self, 200, session.metadata())
                return

            static_path = safe_static_path(self.path)
            if static_path is None or not static_path.is_file():
                self.send_error(404, "Not found")
                return

            content_type = mimetypes.guess_type(static_path.name)[0] or "application/octet-stream"
            body = static_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            try:
                payload = read_json_body(self)
            except json.JSONDecodeError:
                json_response(self, 400, {"error": "invalid_json"})
                return

            if self.path.startswith("/api/new"):
                session.reset_transcript()
                json_response(self, 200, {"metadata": session.metadata()})
                return

            if self.path.startswith("/api/chat"):
                user_text = str(payload.get("message") or "").strip()
                if not user_text:
                    json_response(self, 400, {"error": "empty_message"})
                    return
                json_response(self, 200, session.run_turn(user_text))
                return

            json_response(self, 404, {"error": "not_found"})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Local HTML UI for the research agent.")
    parser.add_argument("--provider", choices=["openrouter", "openai", "anthropic", "gemini"], default="gemini")
    parser.add_argument("--model", default=None)
    parser.add_argument("--version", default="ui")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--history-window", type=int, default=5)
    parser.add_argument("--max-tool-rounds", type=int, default=4)
    parser.add_argument("--system-prompt", type=Path, default=ARTIFACTS_DIR / "system_prompt.md")
    parser.add_argument("--tools", type=Path, default=ARTIFACTS_DIR / "tools.yaml")
    args = parser.parse_args()

    session = AgentSession(
        provider_name=args.provider,
        model=args.model,
        version=args.version,
        history_window=args.history_window,
        max_tool_rounds=args.max_tool_rounds,
        system_prompt_path=args.system_prompt,
        tools_path=args.tools,
    )
    server = ThreadingHTTPServer((args.host, args.port), make_handler(session))
    url = f"http://{args.host}:{args.port}"
    print(f"Research Agent UI running at {url}")
    print(f"Transcript: {session.transcript_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping UI server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
