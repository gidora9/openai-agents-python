from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import struct
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field
from typing_extensions import assert_never

from agents import Agent, Runner
from agents.realtime import RealtimeRunner, RealtimeSession, RealtimeSessionEvent
from agents.realtime.config import RealtimeUserInputMessage
from agents.realtime.items import RealtimeItem
from agents.realtime.model import RealtimeModelConfig
from agents.realtime.model_inputs import RealtimeModelSendRawMessage
from agents.version import __version__ as agents_version

if TYPE_CHECKING:
    from examples.realtime.app.agent import get_starting_agent
else:
    from examples.realtime.app.agent import get_starting_agent

DEFAULT_INSTRUCTIONS = os.getenv(
    "AGENT_INSTRUCTIONS",
    "You are a concise, practical assistant. Answer directly and ask for clarification only "
    "when the request cannot be completed safely without it.",
)
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY")
STATIC_DIR = Path(__file__).resolve().parents[2] / "examples" / "realtime" / "app" / "static"
logger = logging.getLogger(__name__)

app = FastAPI(title="OpenAI Agents Service", version="0.1.0")

INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Open Agents Service</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #080a0d;
      --panel: #11151b;
      --panel-2: #151a21;
      --line: #26313d;
      --line-soft: #1d252e;
      --text: #eef3f8;
      --muted: #95a3b3;
      --accent: #7dd3fc;
      --accent-2: #a7f3d0;
      --danger: #fca5a5;
      font-family:
        Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * {
      box-sizing: border-box;
    }

    body {
      min-height: 100vh;
      margin: 0;
      background:
        radial-gradient(circle at 80% 0%, rgba(125, 211, 252, 0.14), transparent 28rem),
        linear-gradient(180deg, #0b0f14 0%, var(--bg) 54%);
      color: var(--text);
    }

    main {
      width: min(1180px, calc(100% - 32px));
      min-height: 100vh;
      margin: 0 auto;
      padding: 28px 0;
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: 24px;
    }

    header,
    footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .mark {
      width: 34px;
      height: 34px;
      border: 1px solid var(--line);
      background: linear-gradient(135deg, #101820, #1e2933);
      display: grid;
      place-items: center;
      color: var(--accent);
      font-weight: 700;
    }

    h1,
    p {
      margin: 0;
    }

    h1 {
      font-size: clamp(22px, 3vw, 42px);
      line-height: 1.04;
      font-weight: 650;
      letter-spacing: 0;
    }

    .subtitle {
      margin-top: 10px;
      max-width: 650px;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.6;
    }

    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      white-space: nowrap;
      border: 1px solid var(--line);
      background: rgba(17, 21, 27, 0.8);
      color: var(--muted);
      padding: 8px 10px;
      font-size: 13px;
    }

    .dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--accent-2);
      box-shadow: 0 0 18px rgba(167, 243, 208, 0.8);
    }

    .workspace {
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr) 280px;
      gap: 14px;
      min-height: 620px;
    }

    .panel {
      border: 1px solid var(--line);
      background: rgba(17, 21, 27, 0.92);
      min-width: 0;
    }

    .panel-head {
      height: 48px;
      padding: 0 14px;
      border-bottom: 1px solid var(--line-soft);
      display: flex;
      align-items: center;
      justify-content: space-between;
      color: var(--muted);
      font-size: 13px;
    }

    .session-list,
    .tools {
      padding: 10px;
      display: grid;
      gap: 8px;
    }

    .session {
      border: 1px solid var(--line-soft);
      background: var(--panel-2);
      padding: 10px;
      display: grid;
      gap: 6px;
    }

    .session.active {
      border-color: rgba(125, 211, 252, 0.55);
    }

    .session-row,
    .tool-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-width: 0;
    }

    .label {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 13px;
    }

    .meta {
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }

    .chat {
      display: grid;
      grid-template-rows: auto 1fr auto;
      overflow: hidden;
    }

    .hero {
      padding: 22px;
      border-bottom: 1px solid var(--line-soft);
      background: linear-gradient(180deg, rgba(125, 211, 252, 0.08), transparent);
    }

    .messages {
      padding: 16px;
      overflow: auto;
      display: grid;
      align-content: start;
      gap: 12px;
    }

    .message {
      max-width: 78%;
      border: 1px solid var(--line-soft);
      background: var(--panel-2);
      padding: 12px;
      font-size: 14px;
      line-height: 1.55;
      white-space: pre-wrap;
    }

    .message.user {
      justify-self: end;
      border-color: rgba(125, 211, 252, 0.45);
      background: #10202b;
    }

    .message.error {
      border-color: rgba(252, 165, 165, 0.5);
      color: var(--danger);
    }

    form {
      padding: 12px;
      border-top: 1px solid var(--line-soft);
      display: grid;
      gap: 10px;
      background: rgba(8, 10, 13, 0.72);
    }

    textarea,
    input {
      width: 100%;
      border: 1px solid var(--line);
      background: #0b1016;
      color: var(--text);
      font: inherit;
      resize: vertical;
      outline: none;
    }

    textarea {
      min-height: 82px;
      max-height: 220px;
      padding: 12px;
      line-height: 1.45;
    }

    input {
      height: 38px;
      padding: 0 10px;
      font-size: 13px;
    }

    .controls {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
    }

    button {
      height: 38px;
      border: 1px solid rgba(125, 211, 252, 0.65);
      background: #dff7ff;
      color: #071015;
      padding: 0 14px;
      font: inherit;
      font-weight: 650;
      cursor: pointer;
    }

    button:disabled {
      cursor: wait;
      opacity: 0.6;
    }

    .tool-row {
      border: 1px solid var(--line-soft);
      background: var(--panel-2);
      padding: 9px 10px;
    }

    .pill {
      color: var(--accent-2);
      font-size: 12px;
    }

    footer {
      color: var(--muted);
      font-size: 12px;
    }

    a {
      color: var(--accent);
      text-decoration: none;
    }

    @media (max-width: 980px) {
      .workspace {
        grid-template-columns: 1fr;
      }

      .workspace > .panel:first-child,
      .workspace > .panel:last-child {
        display: none;
      }
    }

    @media (max-width: 640px) {
      main {
        width: min(100% - 20px, 1180px);
        padding: 16px 0;
      }

      header {
        align-items: flex-start;
        flex-direction: column;
      }

      .workspace {
        min-height: 72vh;
      }

      .message {
        max-width: 92%;
      }

      .controls {
        grid-template-columns: 1fr;
      }

      button {
        width: 100%;
      }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div class="brand">
        <div class="mark">OA</div>
        <div>
          <div class="meta">openai-agents-python / deployed service</div>
          <h1>Open Agents.</h1>
        </div>
      </div>
      <div class="status"><span class="dot"></span><span id="health">checking</span></div>
    </header>

    <section class="workspace" aria-label="Agent workspace">
      <aside class="panel">
        <div class="panel-head"><span>Sessions</span><span>+</span></div>
        <div class="session-list">
          <div class="session active">
            <div class="session-row">
              <span class="label">Agent chat</span><span class="meta">active</span>
            </div>
            <div class="meta">default deployed assistant</div>
          </div>
          <div class="session">
            <div class="session-row">
              <span class="label">API health</span><span class="meta">now</span>
            </div>
            <div class="meta">FastAPI + Agents SDK</div>
          </div>
          <div class="session">
            <div class="session-row">
              <span class="label">Production</span><span class="meta">Vercel</span>
            </div>
            <div class="meta">serverless runtime</div>
          </div>
        </div>
      </aside>

      <section class="panel chat">
        <div class="hero">
          <h1>Spawn a cloud agent.</h1>
          <p class="subtitle">
            Send a task to your deployed OpenAI Agents SDK service. The OpenAI API key stays on
            the server, and this page calls the same production runtime as `/run`.
          </p>
        </div>
        <div id="messages" class="messages">
          <div class="message">
            Describe a task, ask a question, or test the deployed agent. Responses appear here.
          </div>
        </div>
        <form id="chat-form">
          <textarea
            id="message"
            name="message"
            placeholder="Ask the agent to plan, write, analyze, or explain..."
            required
          ></textarea>
          <input
            id="service-key"
            name="service-key"
            placeholder="service key"
            type="password"
            autocomplete="off"
          />
          <div class="controls">
            <input id="model" name="model" placeholder="optional model override" />
            <button id="send" type="submit">Run agent</button>
          </div>
        </form>
      </section>

      <aside class="panel">
        <div class="panel-head"><span>Runtime</span><span id="sdk-version">SDK</span></div>
        <div class="tools">
          <div class="tool-row">
            <span class="label">Responses API</span><span class="pill">ready</span>
          </div>
          <div class="tool-row">
            <span class="label">Server auth</span><span class="pill">hidden</span>
          </div>
          <div class="tool-row">
            <span class="label">FastAPI</span><span class="pill">live</span>
          </div>
          <div class="tool-row">
            <span class="label">Vercel</span><span class="pill">prod</span>
          </div>
        </div>
      </aside>
    </section>

    <footer>
      <span>Inspired by the Open Agents demo layout.</span>
      <a href="/health">health</a>
    </footer>
  </main>

  <script>
    const form = document.querySelector("#chat-form");
    const input = document.querySelector("#message");
    const model = document.querySelector("#model");
    const serviceKey = document.querySelector("#service-key");
    const button = document.querySelector("#send");
    const messages = document.querySelector("#messages");
    const health = document.querySelector("#health");
    const sdkVersion = document.querySelector("#sdk-version");

    function addMessage(text, className = "") {
      const node = document.createElement("div");
      node.className = `message ${className}`.trim();
      node.textContent = text;
      messages.appendChild(node);
      messages.scrollTop = messages.scrollHeight;
      return node;
    }

    async function checkHealth() {
      try {
        const response = await fetch("/health");
        const body = await response.json();
        health.textContent = body.status === "ok" ? "online" : "degraded";
        sdkVersion.textContent = body.agents_sdk_version;
      } catch {
        health.textContent = "offline";
      }
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = input.value.trim();
      const selectedModel = model.value.trim();
      const selectedServiceKey =
        serviceKey.value.trim() || localStorage.getItem("service-key") || "";
      if (!message) return;
      if (!selectedServiceKey) {
        addMessage("Enter the service key before running the agent.", "error");
        serviceKey.focus();
        return;
      }

      addMessage(message, "user");
      localStorage.setItem("service-key", selectedServiceKey);
      input.value = "";
      button.disabled = true;
      button.textContent = "Running";
      const pending = addMessage("Agent is working...");

      try {
        const response = await fetch("/run", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${selectedServiceKey}`,
          },
          body: JSON.stringify({
            message,
            model: selectedModel || null,
          }),
        });
        const body = await response.json();
        if (!response.ok) {
          throw new Error(body.detail || "Agent request failed.");
        }
        pending.textContent = body.output;
      } catch (error) {
        pending.classList.add("error");
        pending.textContent = error.message || "Agent request failed.";
      } finally {
        button.disabled = false;
        button.textContent = "Run agent";
        input.focus();
      }
    });

    checkHealth();
    serviceKey.value = localStorage.getItem("service-key") || "";
  </script>
</body>
</html>
"""


class RunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    instructions: str | None = Field(default=None, max_length=20_000)
    model: str | None = Field(default=None, max_length=200)


class RunResponse(BaseModel):
    output: str
    model: str | None
    agents_sdk_version: str


class RealtimeWebSocketManager:
    def __init__(self) -> None:
        self.active_sessions: dict[str, RealtimeSession] = {}
        self.session_contexts: dict[str, Any] = {}
        self.websockets: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        self.websockets[session_id] = websocket

        agent = get_starting_agent()
        runner = RealtimeRunner(agent)
        model_config: RealtimeModelConfig = {
            "initial_model_settings": {
                "model_name": os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-1.5"),
                "turn_detection": {
                    "type": "server_vad",
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                    "interrupt_response": True,
                    "create_response": True,
                },
            },
        }
        session_context = await runner.run(model_config=model_config)
        session = await session_context.__aenter__()
        self.active_sessions[session_id] = session
        self.session_contexts[session_id] = session_context

        asyncio.create_task(self._process_events(session_id))

    async def disconnect(self, session_id: str) -> None:
        if session_id in self.session_contexts:
            await self.session_contexts[session_id].__aexit__(None, None, None)
            del self.session_contexts[session_id]
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        if session_id in self.websockets:
            del self.websockets[session_id]

    async def send_audio(self, session_id: str, audio_bytes: bytes) -> None:
        if session_id in self.active_sessions:
            await self.active_sessions[session_id].send_audio(audio_bytes)

    async def send_client_event(self, session_id: str, event: dict[str, Any]) -> None:
        session = self.active_sessions.get(session_id)
        if not session:
            return
        await session.model.send_event(
            RealtimeModelSendRawMessage(
                message={
                    "type": event["type"],
                    "other_data": {k: v for k, v in event.items() if k != "type"},
                }
            )
        )

    async def send_user_message(
        self,
        session_id: str,
        message: RealtimeUserInputMessage,
    ) -> None:
        session = self.active_sessions.get(session_id)
        if not session:
            return
        await session.send_message(message)

    async def approve_tool_call(
        self,
        session_id: str,
        call_id: str,
        *,
        always: bool = False,
    ) -> None:
        session = self.active_sessions.get(session_id)
        if session:
            await session.approve_tool_call(call_id, always=always)

    async def reject_tool_call(
        self,
        session_id: str,
        call_id: str,
        *,
        always: bool = False,
    ) -> None:
        session = self.active_sessions.get(session_id)
        if session:
            await session.reject_tool_call(call_id, always=always)

    async def interrupt(self, session_id: str) -> None:
        session = self.active_sessions.get(session_id)
        if session:
            await session.interrupt()

    async def _process_events(self, session_id: str) -> None:
        try:
            session = self.active_sessions[session_id]
            websocket = self.websockets[session_id]

            async for event in session:
                event_data = await self._serialize_event(event)
                await websocket.send_text(json.dumps(event_data))
        except Exception as exc:
            logger.error("Error processing realtime events for %s: %s", session_id, exc)

    def _sanitize_history_item(self, item: RealtimeItem) -> dict[str, Any]:
        item_dict = item.model_dump()
        content = item_dict.get("content")
        if isinstance(content, list):
            sanitized_content: list[Any] = []
            for part in content:
                if isinstance(part, dict):
                    sanitized_part = part.copy()
                    if sanitized_part.get("type") in {"audio", "input_audio"}:
                        sanitized_part.pop("audio", None)
                    sanitized_content.append(sanitized_part)
                else:
                    sanitized_content.append(part)
            item_dict["content"] = sanitized_content
        return item_dict

    async def _serialize_event(self, event: RealtimeSessionEvent) -> dict[str, Any]:
        base_event: dict[str, Any] = {"type": event.type}

        if event.type == "agent_start":
            base_event["agent"] = event.agent.name
        elif event.type == "agent_end":
            base_event["agent"] = event.agent.name
        elif event.type == "handoff":
            base_event["from"] = event.from_agent.name
            base_event["to"] = event.to_agent.name
        elif event.type == "tool_start":
            base_event["tool"] = event.tool.name
        elif event.type == "tool_end":
            base_event["tool"] = event.tool.name
            base_event["output"] = str(event.output)
        elif event.type == "tool_approval_required":
            base_event["tool"] = event.tool.name
            base_event["call_id"] = event.call_id
            base_event["arguments"] = event.arguments
            base_event["agent"] = event.agent.name
        elif event.type == "audio":
            base_event["audio"] = base64.b64encode(event.audio.data).decode("utf-8")
        elif event.type == "audio_interrupted":
            pass
        elif event.type == "audio_end":
            pass
        elif event.type == "history_updated":
            base_event["history"] = [self._sanitize_history_item(item) for item in event.history]
        elif event.type == "history_added":
            try:
                base_event["item"] = self._sanitize_history_item(event.item)
            except Exception:
                base_event["item"] = None
        elif event.type == "guardrail_tripped":
            base_event["guardrail_results"] = [
                {"name": result.guardrail.name} for result in event.guardrail_results
            ]
        elif event.type == "raw_model_event":
            base_event["raw_model_event"] = {"type": event.data.type}
        elif event.type == "error":
            base_event["error"] = str(event.error) if hasattr(event, "error") else "Unknown error"
        elif event.type == "input_audio_timeout_triggered":
            pass
        else:
            assert_never(event)

        return base_event


realtime_manager = RealtimeWebSocketManager()


@app.get("/", response_class=HTMLResponse)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/app.js", include_in_schema=False)
async def realtime_app_js() -> Response:
    js = (STATIC_DIR / "app.js").read_text()
    js = js.replace(
        "new WebSocket(`ws://localhost:8000/ws/${this.sessionId}`)",
        "new WebSocket(`${window.location.protocol === 'https:' ? 'wss' : 'ws'}://"
        "${window.location.host}/ws/${this.sessionId}`)",
    )
    return Response(content=js, media_type="application/javascript")


@app.get("/audio-recorder.worklet.js", include_in_schema=False)
async def audio_recorder_worklet() -> FileResponse:
    return FileResponse(STATIC_DIR / "audio-recorder.worklet.js")


@app.get("/audio-playback.worklet.js", include_in_schema=False)
async def audio_playback_worklet() -> FileResponse:
    return FileResponse(STATIC_DIR / "audio-playback.worklet.js")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" fill="#080a0d"/>'
        '<path d="M8 17a8 8 0 1 1 16 0v6H8z" fill="#7dd3fc"/>'
        '<circle cx="16" cy="14" r="4" fill="#080a0d"/>'
        "</svg>"
    )
    return Response(content=svg, media_type="image/svg+xml")


def require_service_key(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if SERVICE_API_KEY is None:
        return

    expected = f"Bearer {SERVICE_API_KEY}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid service API key.",
        )


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "agents_sdk_version": agents_version,
    }


@app.post("/run", response_model=RunResponse, dependencies=[Depends(require_service_key)])
async def run_agent(request: RunRequest) -> RunResponse:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENAI_API_KEY is not configured.",
        )

    model = request.model or os.getenv("OPENAI_AGENT_MODEL")
    agent_kwargs: dict[str, object] = {
        "name": "Deployed Assistant",
        "instructions": request.instructions or DEFAULT_INSTRUCTIONS,
    }
    if model:
        agent_kwargs["model"] = model

    agent = Agent(**agent_kwargs)
    result = await Runner.run(agent, request.message)
    return RunResponse(
        output=str(result.final_output),
        model=model,
        agents_sdk_version=agents_version,
    )


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    await realtime_manager.connect(websocket, session_id)
    image_buffers: dict[str, dict[str, Any]] = {}
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message["type"] == "audio":
                int16_data = message["data"]
                audio_bytes = struct.pack(f"{len(int16_data)}h", *int16_data)
                await realtime_manager.send_audio(session_id, audio_bytes)
            elif message["type"] == "commit_audio":
                await realtime_manager.send_client_event(
                    session_id,
                    {"type": "input_audio_buffer.commit"},
                )
            elif message["type"] == "image":
                data_url = message.get("data_url")
                prompt_text = message.get("text") or "Please describe this image."
                if not data_url:
                    await websocket.send_text(
                        json.dumps({"type": "error", "error": "No data_url for image message."})
                    )
                    continue
                await realtime_manager.send_user_message(
                    session_id,
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_image", "image_url": data_url, "detail": "high"},
                            {"type": "input_text", "text": prompt_text},
                        ],
                    },
                )
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "client_info",
                            "info": "image_enqueued",
                            "size": len(data_url),
                        }
                    )
                )
            elif message["type"] == "image_start":
                img_id = str(message.get("id"))
                image_buffers[img_id] = {
                    "text": message.get("text") or "Please describe this image.",
                    "chunks": [],
                }
                await websocket.send_text(
                    json.dumps({"type": "client_info", "info": "image_start_ack", "id": img_id})
                )
            elif message["type"] == "image_chunk":
                img_id = str(message.get("id"))
                chunk = message.get("chunk", "")
                if img_id in image_buffers:
                    image_buffers[img_id]["chunks"].append(chunk)
            elif message["type"] == "image_end":
                img_id = str(message.get("id"))
                buf = image_buffers.pop(img_id, None)
                if buf is None:
                    await websocket.send_text(
                        json.dumps({"type": "error", "error": "Unknown image id for image_end."})
                    )
                    continue
                data_url = "".join(buf["chunks"]) if buf["chunks"] else None
                if not data_url:
                    await websocket.send_text(
                        json.dumps({"type": "error", "error": "Empty image."})
                    )
                    continue
                await realtime_manager.send_user_message(
                    session_id,
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_image", "image_url": data_url, "detail": "high"},
                            {"type": "input_text", "text": buf["text"]},
                        ],
                    },
                )
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "client_info",
                            "info": "image_enqueued",
                            "id": img_id,
                            "size": len(data_url),
                        }
                    )
                )
            elif message["type"] == "tool_approval_decision":
                call_id = message.get("call_id")
                approve = bool(message.get("approve"))
                always = bool(message.get("always", False))
                if not call_id:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "error": "Missing call_id for tool approval decision.",
                            }
                        )
                    )
                    continue
                if approve:
                    await realtime_manager.approve_tool_call(session_id, call_id, always=always)
                else:
                    await realtime_manager.reject_tool_call(session_id, call_id, always=always)
            elif message["type"] == "interrupt":
                await realtime_manager.interrupt(session_id)

    except WebSocketDisconnect:
        await realtime_manager.disconnect(session_id)
