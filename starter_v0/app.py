from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from chat import (
    assistant_tool_message,
    execute_tool_call,
    json_text,
    now_iso,
    run_model_tool_loop,
    safe_slug,
    tool_results_message,
    trim_history,
    write_transcript,
)
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version

# Set page config
st.set_page_config(
    page_title="AI Research Agent — Evidence Workbench",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("<div id='main-app-top'></div><a href='#main-app-top' class='back-to-top'>⬆️ Top</a>", unsafe_allow_html=True)


# Custom CSS for theme-adaptive (Light & Dark mode) aesthetics and evidence layout
st.markdown(
    """
    <style>
    /* Adaptive Header title styling */
    .app-header {
        background: var(--secondary-background-color, rgba(240, 242, 246, 0.8));
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 20px 24px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        margin-bottom: 24px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
    }
    .app-title {
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 1.85rem;
        font-weight: 800;
        background: linear-gradient(90deg, #2563eb, #7c3aed);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .app-subtitle {
        color: var(--text-color, #334155);
        opacity: 0.85;
        font-size: 0.95rem;
        margin-top: 6px;
    }
    
    /* Metadata badge */
    .meta-badge {
        display: inline-block;
        background: var(--secondary-background-color, #f1f5f9);
        color: #2563eb;
        font-family: monospace;
        font-size: 0.82rem;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 6px;
        border: 1px solid rgba(37, 99, 235, 0.3);
        margin-right: 6px;
        margin-bottom: 6px;
    }
    
    /* Tool trace card */
    .tool-trace-card {
        background: var(--secondary-background-color, #f8fafc);
        border-left: 4px solid #2563eb;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 10px 0;
        font-family: monospace;
        font-size: 0.88rem;
        color: var(--text-color);
    }
    .tool-trace-card.error {
        border-left-color: #ef4444;
    }
    
    /* Tool badge */
    .tool-tag {
        background: #059669;
        color: #ffffff !important;
        font-weight: 600;
        font-size: 0.8rem;
        padding: 2px 8px;
        border-radius: 4px;
        font-family: monospace;
    }
    /* Floating Jump to Top button fixed at bottom-right */
    .back-to-top {
        position: fixed;
        bottom: 28px;
        right: 28px;
        background: var(--secondary-background-color, #ffffff);
        color: #2563eb !important;
        border: 2px solid #2563eb;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
        border-radius: 30px;
        padding: 10px 20px;
        font-size: 0.9rem;
        font-weight: 700;
        text-decoration: none !important;
        z-index: 99999;
        transition: all 0.2s ease-in-out;
        cursor: pointer;
    }
    .back-to-top:hover {
        background: #2563eb;
        color: #ffffff !important;
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(37, 99, 235, 0.4);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
load_lab_env(ROOT)

# Sidebar Configuration
with st.sidebar:
    st.image("https://img.icons8.com/fluent/96/000000/artificial-intelligence.png", width=64)
    st.title("Agent Config")
    st.markdown("---")

    provider_name = st.selectbox(
        "Model Provider",
        options=["openai", "gemini", "openrouter", "anthropic"],
        index=0,
        help="Select live LLM provider configured in .env",
    )

    custom_model = st.text_input(
        "Model Override (Optional)",
        value="",
        placeholder="e.g. gpt-4o-mini",
        help="Leave empty for provider default",
    )

    version_label = st.text_input(
        "Artifact Version Label",
        value="v0",
        help="Version tag for logging (e.g. v0, v1, v2)",
    )

    st.markdown("### Agent Parameters")
    history_window = st.slider("History Window", min_value=1, max_value=10, value=5)
    max_tool_rounds = st.slider("Max Tool Rounds", min_value=1, max_value=8, value=4)

    st.markdown("---")
    
    # Load artifact metadata
    system_prompt_path = ARTIFACTS_DIR / "system_prompt.md"
    tools_path = ARTIFACTS_DIR / "tools.yaml"
    
    system_prompt_text = system_prompt_path.read_text(encoding="utf-8") if system_prompt_path.exists() else ""
    tool_decls = load_tool_declarations(tools_path) if tools_path.exists() else []
    
    artifact_version = build_artifact_version(version_label, system_prompt_path, tools_path)
    
    st.markdown("### Artifact Metadata")
    st.markdown(f"<span class='meta-badge'>Ver: {artifact_version.artifact_version}</span>", unsafe_allow_html=True)
    st.markdown(f"<span class='meta-badge'>Prompt Hash: {artifact_version.prompt_hash[:8]}</span>", unsafe_allow_html=True)
    st.markdown(f"<span class='meta-badge'>Tools Hash: {artifact_version.tools_hash[:8]}</span>", unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🔄 Reset Chat Session", use_container_width=True, type="secondary"):
        for key in ["messages", "chat_history", "transcript", "transcript_path", "history"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

# Initialize Session State
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "history" not in st.session_state:
    st.session_state.history = []

if "transcript" not in st.session_state or st.session_state.get("version") != version_label:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join([safe_slug(version_label), safe_slug(provider_name), timestamp])
    transcript_path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
    
    provider_inst = make_provider(provider_name)
    selected_model = custom_model or getattr(provider_inst, "default_model", None)

    st.session_state.transcript_path = transcript_path
    st.session_state.version = version_label
    st.session_state.transcript = {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact_version),
        "provider": provider_name,
        "model": selected_model,
        "system_prompt": str(system_prompt_path),
        "tools": str(tools_path),
        "history_window": history_window,
        "max_tool_rounds": max_tool_rounds,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }

# App Layout
tab_chat, tab_inspector = st.tabs(["💬 Research Agent Chat", "📊 Transcript & Evidence Inspector"])

with tab_chat:
    st.markdown(
        f"""
        <div class="app-header">
            <h1 class="app-title">🔍 Day 04 Research Agent Workbench</h1>
            <div class="app-subtitle">
                Interactive tool execution, evidence trace logging, and live multi-turn research agent.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Render Chat History
    for turn in st.session_state.chat_history:
        role = turn["role"]
        content = turn.get("content", "")
        
        if role == "user":
            with st.chat_message("user"):
                st.write(content)
        else:
            with st.chat_message("assistant"):
                # Render tool trace if available
                tool_events = turn.get("tool_events", [])
                rounds = turn.get("rounds", [])

                if tool_events or rounds:
                    with st.expander(f"🛠️ Tool Execution Trace ({len(tool_events)} events, {len(rounds)} rounds)", expanded=False):
                        for r in rounds:
                            st.markdown(f"**Round {r.get('round')}**")
                            for call in r.get("tool_calls", []):
                                st.markdown(f"- Tool: `<span class='tool-tag'>{call.get('name')}</span>`", unsafe_allow_html=True)
                                st.json(call.get("args"))
                            
                            for res in r.get("tool_results", []):
                                result_data = res.get("result", {})
                                is_err = isinstance(result_data, dict) and result_data.get("error") is not None
                                err_status = f" ❌ Error: {result_data.get('error')}" if is_err else " ✅ Success"
                                with st.popover(f"Result: {res.get('tool')}{err_status}"):
                                    st.json(result_data)

                # Render final text answer
                if turn.get("status") == "waiting_for_user":
                    st.warning(f"❓ **Cần thông tin bổ sung / Xác nhận:** {content}")
                else:
                    st.markdown(content)

    # User Input Form
    if user_prompt := st.chat_input("Nhập câu hỏi nghiên cứu (ví dụ: 'Tweet mới nhất của Sam Altman là gì?')..."):
        # Display user message
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.write(user_prompt)

        # Prepare messages context
        messages = [
            {"role": "system", "content": system_prompt_text},
            *trim_history(st.session_state.history, history_window),
            {"role": "user", "content": user_prompt},
        ]

        openai_tools = to_openai_tools(tool_decls)
        provider = make_provider(provider_name)

        # Execute agent loop with spinner
        with st.chat_message("assistant"):
            with st.spinner("🤖 Agent đang suy nghĩ và gọi tools..."):
                turn_index = len(st.session_state.transcript["turns"]) + 1
                turn_record: dict[str, Any] = {
                    "turn_index": turn_index,
                    "started_at": now_iso(),
                    "user": user_prompt,
                    "status": "started",
                    "assistant_text": None,
                    "rounds": [],
                    "tool_events": [],
                }

                try:
                    result = run_model_tool_loop(
                        provider=provider,
                        messages=messages,
                        tools=openai_tools,
                        model=custom_model or None,
                        max_tool_rounds=max_tool_rounds,
                    )
                    turn_record.update(result)
                    assistant_text = result["assistant_text"]

                    st.session_state.history.append({"role": "user", "content": user_prompt})
                    st.session_state.history.append({"role": "assistant", "content": assistant_text})

                except Exception as exc:
                    assistant_text = f"Provider Error: {exc}"
                    turn_record.update({
                        "status": "provider_error",
                        "error": f"{type(exc).__name__}: {str(exc)}",
                        "assistant_text": assistant_text,
                    })

                turn_record["ended_at"] = now_iso()
                st.session_state.transcript["turns"].append(turn_record)
                write_transcript(st.session_state.transcript_path, st.session_state.transcript)

                # Append to chat history UI
                ui_turn = {
                    "role": "assistant",
                    "content": assistant_text,
                    "status": turn_record.get("status"),
                    "rounds": turn_record.get("rounds", []),
                    "tool_events": turn_record.get("tool_events", []),
                }
                st.session_state.chat_history.append(ui_turn)
                st.rerun()

with tab_inspector:
    st.header("📊 Transcript & Evidence Inspector")
    st.markdown("Xem lại chi tiết bằng chứng JSON log của các phiên chạy agent.")

    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    transcript_files = sorted(list(TRANSCRIPTS_DIR.glob("*.json")), reverse=True)

    if not transcript_files:
        st.info("Chưa có file transcript nào được lưu. Hãy thực hiện một câu lệnh trong tab Chat!")
    else:
        # Initialize selectbox state key if missing or invalid
        if "inspector_selectbox" not in st.session_state or st.session_state["inspector_selectbox"] not in transcript_files:
            st.session_state["inspector_selectbox"] = transcript_files[0]

        # Action buttons for quick navigation
        col_act1, col_act2 = st.columns([1, 1])

        with col_act1:
            if st.button("⚡ Xem Log mới nhất (Latest)", use_container_width=True, type="primary"):
                st.session_state["inspector_selectbox"] = transcript_files[0]
                st.rerun()

        with col_act2:
            current_path = st.session_state.get("transcript_path")
            if current_path in transcript_files:
                if st.button("💬 Xem phiên Chat hiện tại", use_container_width=True):
                    st.session_state["inspector_selectbox"] = current_path
                    st.rerun()

        selected_file = st.selectbox(
            "Chọn file Transcript JSON:",
            options=transcript_files,
            key="inspector_selectbox",
            format_func=lambda p: f"{'🔴 [Hiện tại] ' if p == st.session_state.get('transcript_path') else '📄 '}{p.name}",
        )

        if selected_file:
            try:
                content = json.loads(selected_file.read_text(encoding="utf-8"))
                col1, col2, col3 = st.columns(3)
                col1.metric("Provider", content.get("provider", "N/A"))
                col2.metric("Artifact Version", content.get("artifact_version", "N/A"))
                col3.metric("Turns Count", len(content.get("turns", [])))

                st.markdown("---")
                st.markdown("### Raw JSON Content & Evidence")
                st.json(content)
            except Exception as e:
                st.error(f"Lỗi đọc file: {e}")


