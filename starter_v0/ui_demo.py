from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from env_loader import load_lab_env
from providers import make_provider
from run_eval import (
    case_messages,
    evaluate_phase_b,
    load_cases,
    load_dataset_info,
    safe_slug,
    summarize,
    validate_expected_tools,
)
from tools import TOOL_FUNCTIONS, load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
DATA_DIR = ROOT / "data"
RUNS_DIR = ROOT / "runs"
TRANSCRIPTS_DIR = ROOT / "transcripts"

load_lab_env(ROOT)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def resolve_path(raw_value: str, default_path: Path) -> Path:
    raw_value = raw_value.strip()
    if not raw_value:
        return default_path
    path = Path(raw_value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def tool_names(calls: list[dict[str, Any]]) -> str:
    return "|".join(call.get("name", "") for call in calls)


def expected_tool_names(expect: dict[str, Any]) -> str:
    calls = expect.get("tool_calls") or []
    if not calls:
        return "no_tool" if expect.get("no_tool") else ""
    return "|".join(call.get("name", "") for call in calls)


def execute_tool_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return {
            "tool": name,
            "args": args,
            "result": {"error": "unknown_tool", "message": f"No local implementation for {name}"},
        }
    try:
        result = func(**args)
    except Exception as exc:
        result = {"error": type(exc).__name__, "message": str(exc)}
    return {"tool": name, "args": args, "result": result}


def run_eval_live(
    *,
    provider_name: str,
    version: str,
    suite: str,
    phase: str,
    model: str | None,
    system_prompt_path: Path,
    tools_path: Path,
    eval_cases_path: Path,
) -> tuple[dict[str, Any], Path]:
    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    artifact_version = build_artifact_version(version, system_prompt_path, tools_path)
    provider = make_provider(provider_name)
    selected_model = model or getattr(provider, "default_model", None)
    dataset_info = load_dataset_info(eval_cases_path)
    cases = load_cases(eval_cases_path, phase)
    if not cases:
        raise RuntimeError(f"No cases matched phase={phase!r} in {eval_cases_path}")

    tool_declarations = load_tool_declarations(tools_path)
    validate_expected_tools(cases, tool_declarations, eval_cases_path)
    openai_tools = to_openai_tools(tool_declarations)

    results: list[dict[str, Any]] = []
    progress = st.progress(0.0)
    status = st.empty()

    for index, case in enumerate(cases, start=1):
        status.write(f"Running case {index}/{len(cases)}: {case['id']}")
        try:
            from agent import ResearchAgent

            agent = ResearchAgent(provider, system_prompt=system_prompt, tools=openai_tools, model=model)
            tool_choice = None if case["expect"].get("no_tool") else "required"
            run = agent.run(case_messages(case), tool_choice=tool_choice)
            calls = [{"name": call.name, "args": call.args} for call in run.tool_calls]
            result = evaluate_phase_b(case, calls, run.text)
            tool_results = run.tool_results
        except Exception as exc:
            result = {
                "passed": False,
                "failure_type": "provider_error",
                "case_failure_type": case.get("failure_type"),
                "observed_mismatch": "provider_error",
                "failures": [f"{type(exc).__name__}: {str(exc)}"],
                "actual_tool_calls": [],
                "actual_text": None,
                "routing_correct": False,
                "args_correct": False,
            }
            tool_results = []

        results.append(
            {
                "id": case["id"],
                "phase": case["phase"],
                "suite": suite,
                "case_suite": case.get("suite", suite),
                "is_multiturn": "turns" in case,
                "metadata": case.get("metadata", {}),
                "input": case.get("input") or case.get("query") or case.get("turns"),
                "expect": case["expect"],
                "result": result,
                "tool_results": tool_results,
            }
        )
        progress.progress(index / len(cases))

    summary = summarize(results)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    generated_at = now.isoformat(timespec="seconds")
    timestamp = now.strftime("%Y%m%dT%H%M%S%f")
    run_id = "_".join([
        safe_slug(version),
        safe_slug(phase),
        safe_slug(suite),
        safe_slug(provider_name),
        timestamp,
    ])

    payload: dict[str, Any] = {
        "run_id": run_id,
        "version": version,
        **artifact_version_dict(artifact_version),
        "phase": phase,
        "suite": suite,
        "provider": provider_name,
        "model": selected_model,
        "system_prompt": str(system_prompt_path),
        "tools": str(tools_path),
        "eval_cases": str(eval_cases_path),
        **dataset_info,
        "generated_at": generated_at,
        "summary": summary,
        "results": results,
    }

    out_path = RUNS_DIR / f"{run_id}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    status.success(f"Done. Saved run: {out_path.name}")
    return payload, out_path


def run_chat_turn(
    *,
    provider_name: str,
    version: str,
    model: str | None,
    system_prompt_path: Path,
    tools_path: Path,
    user_text: str,
    max_tool_rounds: int,
) -> dict[str, Any]:
    provider = make_provider(provider_name)
    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    tool_declarations = load_tool_declarations(tools_path)
    openai_tools = to_openai_tools(tool_declarations)
    artifact_version = build_artifact_version(version, system_prompt_path, tools_path)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    rounds: list[dict[str, Any]] = []
    all_tool_events: list[dict[str, Any]] = []

    for round_index in range(1, max_tool_rounds + 1):
        response = provider.complete(messages, openai_tools, model=model, temperature=0.0)
        calls = [{"name": call.name, "args": call.args} for call in response.tool_calls]
        round_record: dict[str, Any] = {
            "round": round_index,
            "assistant_text": response.text,
            "tool_calls": calls,
            "tool_results": [],
        }

        if not response.tool_calls:
            rounds.append(round_record)
            return {
                "status": "answered",
                "assistant_text": response.text or "",
                "rounds": rounds,
                "tool_events": all_tool_events,
                "artifact_version": artifact_version.artifact_version,
            }

        messages.append(
            {
                "role": "assistant",
                "content": json.dumps({"tool_calls": calls, "assistant_text": response.text}, ensure_ascii=False),
            }
        )

        non_clarification_events: list[dict[str, Any]] = []
        for call in response.tool_calls:
            event = execute_tool_call(call.name, call.args)
            round_record["tool_results"].append(event)
            all_tool_events.append(event)
            result = event.get("result", {})

            if isinstance(result, dict) and result.get("awaiting_user"):
                rounds.append(round_record)
                return {
                    "status": "waiting_for_user",
                    "assistant_text": result.get("question") or "Need more information.",
                    "rounds": rounds,
                    "tool_events": all_tool_events,
                    "artifact_version": artifact_version.artifact_version,
                }

            non_clarification_events.append(event)

        messages.append(
            {
                "role": "user",
                "content": (
                    "TOOL_RESULTS_JSON:\n"
                    f"{json.dumps(non_clarification_events, ensure_ascii=False, indent=2, default=str)}\n\n"
                    "Use only these tool results. If digest requested and items are ready, call format tool."
                ),
            }
        )

        rounds.append(round_record)

    return {
        "status": "max_tool_rounds",
        "assistant_text": f"Stopped after {max_tool_rounds} tool rounds.",
        "rounds": rounds,
        "tool_events": all_tool_events,
        "artifact_version": artifact_version.artifact_version,
    }


def list_json_files(folder: Path, suffix: str = "*.json") -> list[Path]:
    if not folder.exists():
        return []
    return sorted(folder.glob(suffix), key=lambda path: path.stat().st_mtime, reverse=True)


def save_transcript(payload: dict[str, Any], version: str, provider_name: str) -> Path:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join([safe_slug(version), safe_slug(provider_name), "ui", timestamp])
    out_path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return out_path


def render_run_summary(run_payload: dict[str, Any]) -> None:
    summary = run_payload.get("summary", {})
    left, mid, right = st.columns(3)
    left.metric("Case Accuracy", summary.get("case_accuracy", 0.0))
    mid.metric("Passed Cases", summary.get("passed_cases", 0))
    right.metric("Measured Cases", summary.get("measured_cases", 0))

    if summary:
        st.json(summary)

    rows: list[dict[str, Any]] = []
    for item in run_payload.get("results", []):
        result = item.get("result", {})
        rows.append(
            {
                "case_id": item.get("id"),
                "passed": result.get("passed"),
                "failure_type": result.get("failure_type"),
                "observed_mismatch": result.get("observed_mismatch"),
                "expected_tool": expected_tool_names(item.get("expect", {})),
                "actual_tool": tool_names(result.get("actual_tool_calls") or []),
                "failures": "; ".join(result.get("failures") or []),
            }
        )
    if rows:
        st.dataframe(rows, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Research Agent Demo UI", layout="wide")
    st.title("Research Agent Demo UI")
    st.caption("Demo eval, chat tool trace, and artifact inspection in one place.")

    with st.sidebar:
        st.subheader("Config")
        provider_name = st.selectbox("Provider", ["openai", "openrouter", "anthropic", "gemini"], index=0)
        model = st.text_input("Model override (optional)", value="")
        version = st.text_input("Version", value="v_demo")
        suite = st.selectbox("Suite", ["base", "group", "cross", "extension"], index=0)
        phase = st.selectbox("Phase", ["B"], index=0)

        tool_default = ARTIFACTS_DIR / "tools.yaml"
        prompt_default = ARTIFACTS_DIR / "system_prompt.md"
        eval_default = DATA_DIR / "eval_base.json"

        tools_raw = st.text_input("Tools file", value=str(tool_default))
        prompt_raw = st.text_input("System prompt file", value=str(prompt_default))
        eval_raw = st.text_input("Eval cases file", value=str(eval_default))

    tools_path = resolve_path(tools_raw, tool_default)
    prompt_path = resolve_path(prompt_raw, prompt_default)
    eval_path = resolve_path(eval_raw, eval_default)
    model_or_none = model.strip() or None

    tab_eval, tab_chat, tab_inspect = st.tabs(["Run Eval", "Chat Demo", "Inspect Artifacts"])

    with tab_eval:
        st.subheader("Run Live Eval")
        st.write("Run eval with selected provider and save a run JSON into runs/.")
        if st.button("Run Eval Now", type="primary"):
            try:
                with st.spinner("Running eval..."):
                    run_payload, out_path = run_eval_live(
                        provider_name=provider_name,
                        version=version,
                        suite=suite,
                        phase=phase,
                        model=model_or_none,
                        system_prompt_path=prompt_path,
                        tools_path=tools_path,
                        eval_cases_path=eval_path,
                    )
                st.success(f"Saved: {out_path}")
                st.write(f"artifact_version: {run_payload.get('artifact_version')}")
                render_run_summary(run_payload)
                with st.expander("Raw run JSON"):
                    st.json(run_payload)
            except Exception as exc:
                st.error(f"Eval failed: {type(exc).__name__}: {str(exc)}")

    with tab_chat:
        st.subheader("Live Chat Demo")
        st.write("Run one-turn chat with tool execution trace by round.")
        max_tool_rounds = st.slider("Max tool rounds", min_value=1, max_value=8, value=4)
        user_text = st.text_area("User message", value="Tóm tắt 3 bài viết mới về AI safety tuần này")

        if "ui_chat_turns" not in st.session_state:
            st.session_state.ui_chat_turns = []

        if st.button("Send", key="send_chat"):
            if not user_text.strip():
                st.warning("Please enter a message.")
            else:
                try:
                    with st.spinner("Calling model and tools..."):
                        result = run_chat_turn(
                            provider_name=provider_name,
                            version=version,
                            model=model_or_none,
                            system_prompt_path=prompt_path,
                            tools_path=tools_path,
                            user_text=user_text,
                            max_tool_rounds=max_tool_rounds,
                        )
                    turn = {
                        "timestamp": now_iso(),
                        "user": user_text,
                        "assistant": result.get("assistant_text"),
                        "status": result.get("status"),
                        "rounds": result.get("rounds", []),
                        "tool_events": result.get("tool_events", []),
                        "artifact_version": result.get("artifact_version"),
                    }
                    st.session_state.ui_chat_turns.append(turn)
                except Exception as exc:
                    st.error(f"Chat failed: {type(exc).__name__}: {str(exc)}")

        for index, turn in enumerate(reversed(st.session_state.ui_chat_turns), start=1):
            st.markdown(f"### Turn {len(st.session_state.ui_chat_turns) - index + 1}")
            st.write(f"Status: {turn['status']}")
            st.write(f"artifact_version: {turn['artifact_version']}")
            st.write("User:")
            st.code(turn["user"], language="text")
            st.write("Assistant:")
            st.code(turn["assistant"] or "", language="text")
            for round_item in turn["rounds"]:
                with st.expander(f"Round {round_item['round']} trace"):
                    st.write("Tool calls")
                    st.json(round_item.get("tool_calls", []))
                    st.write("Tool results")
                    st.json(round_item.get("tool_results", []))

        if st.session_state.ui_chat_turns:
            if st.button("Save Transcript JSON", key="save_transcript"):
                transcript_payload = {
                    "transcript_id": "ui_session",
                    "provider": provider_name,
                    "model": model_or_none,
                    "version": version,
                    "system_prompt": str(prompt_path),
                    "tools": str(tools_path),
                    "created_at": st.session_state.ui_chat_turns[0]["timestamp"],
                    "updated_at": now_iso(),
                    "turns": st.session_state.ui_chat_turns,
                }
                out_path = save_transcript(transcript_payload, version, provider_name)
                st.success(f"Transcript saved: {out_path}")

    with tab_inspect:
        st.subheader("Inspect Runs & Transcripts")
        run_files = list_json_files(RUNS_DIR, "*.json")
        transcript_files = list_json_files(TRANSCRIPTS_DIR, "*.transcript.json")

        if run_files:
            run_names = [path.name for path in run_files]
            selected_run_name = st.selectbox("Run JSON", run_names)
            selected_run = RUNS_DIR / selected_run_name
            try:
                run_payload = json.loads(selected_run.read_text(encoding="utf-8"))
                st.write(f"Loaded run: {selected_run}")
                st.write(f"artifact_version: {run_payload.get('artifact_version')}")
                render_run_summary(run_payload)
            except Exception as exc:
                st.error(f"Cannot read run: {type(exc).__name__}: {str(exc)}")
        else:
            st.info("No run files found yet in runs/.")

        if transcript_files:
            transcript_names = [path.name for path in transcript_files]
            selected_transcript_name = st.selectbox("Transcript JSON", transcript_names)
            selected_transcript = TRANSCRIPTS_DIR / selected_transcript_name
            try:
                transcript_payload = json.loads(selected_transcript.read_text(encoding="utf-8"))
                st.write(f"Loaded transcript: {selected_transcript}")
                st.json(transcript_payload)
            except Exception as exc:
                st.error(f"Cannot read transcript: {type(exc).__name__}: {str(exc)}")
        else:
            st.info("No transcript files found yet in transcripts/.")


if __name__ == "__main__":
    main()
