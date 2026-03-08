import asyncio
import json
import os
from pathlib import Path
import time
from typing import Any

from dotenv import load_dotenv
import inngest
import requests
import streamlit as st

load_dotenv()

st.set_page_config(
    page_title="RAG Control Panel",
    page_icon="📄",
    layout="wide",
)


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');

            :root {
                --bg-top: #fff7ed;
                --bg-bottom: #ffffff;
                --text-main: #0a0a0a;
                --muted: #3f3f46;
                --brand: #0b63f6;
                --brand-2: #ff6a3d;
                --brand-soft: #dbeafe;
                --border: #d4d4d8;
                --surface: #ffffff;
            }

            .stApp {
                font-family: "Manrope", sans-serif;
                background:
                    radial-gradient(circle at 10% -10%, #fee2e2 0%, transparent 40%),
                    radial-gradient(circle at 100% 0%, #dbeafe 0%, transparent 42%),
                    linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
                color: var(--text-main);
            }

            header[data-testid="stHeader"] {
                background: transparent !important;
            }

            div[data-testid="stToolbar"] {
                background: #ffffff !important;
                border: 1px solid var(--border);
                border-radius: 10px;
            }

            div[data-testid="stDecoration"] {
                background: transparent !important;
            }

            section[data-testid="stSidebar"] {
                background: #ffffff !important;
                border-right: 1px solid var(--border);
            }

            section[data-testid="stSidebar"] * {
                color: #000 !important;
            }

            h1, h2, h3, .hero h1 {
                font-family: "Space Grotesk", sans-serif !important;
                color: #000 !important;
            }

            p, span, label, li, div {
                color: var(--text-main);
            }

            .hero {
                border: 1px solid var(--border);
                border-radius: 18px;
                padding: 1.2rem 1.4rem;
                background: linear-gradient(125deg, #ffffff 0%, #f8fafc 100%);
                box-shadow: 0 10px 28px rgba(11, 99, 246, 0.12);
                margin-bottom: 1rem;
                position: relative;
                overflow: hidden;
            }

            .hero::after {
                content: "";
                position: absolute;
                inset: auto -20% -65% auto;
                width: 320px;
                height: 320px;
                border-radius: 50%;
                background: radial-gradient(circle, rgba(255,106,61,0.18), transparent 70%);
                pointer-events: none;
            }

            .hero h1 {
                margin: 0;
                font-size: 2rem;
                letter-spacing: -0.02em;
            }

            .hero p {
                margin: 0.4rem 0 0 0;
                color: var(--muted);
                font-size: 0.98rem;
            }

            .landing-hero {
                border: 1px solid var(--border);
                border-radius: 20px;
                padding: 2rem 1.5rem;
                background: linear-gradient(125deg, #ffffff 0%, #eef4ff 45%, #fff1eb 100%);
                box-shadow: 0 16px 36px rgba(11, 99, 246, 0.14);
                position: relative;
                overflow: hidden;
                margin-bottom: 1rem;
            }

            .landing-hero h1 {
                font-size: 2.25rem;
                margin: 0 0 0.55rem 0;
                line-height: 1.05;
            }

            .landing-hero p {
                max-width: 760px;
                margin: 0;
                font-size: 1rem;
                color: var(--muted);
            }

            .landing-pill {
                display: inline-block;
                background: #e0ecff;
                border: 1px solid #bcd3ff;
                color: #0a2d74;
                font-weight: 700;
                border-radius: 999px;
                padding: 0.28rem 0.6rem;
                margin-bottom: 0.8rem;
                font-size: 0.84rem;
            }

            .kpi-strip {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.7rem;
                margin: 0 0 1rem 0;
            }

            .kpi {
                border: 1px solid var(--border);
                border-radius: 12px;
                background: #fff;
                padding: 0.8rem 0.9rem;
            }

            .kpi h3 {
                margin: 0;
                font-size: 1.2rem;
            }

            .kpi p {
                margin: 0.2rem 0 0 0;
                color: var(--muted);
                font-size: 0.9rem;
            }

            .value-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.8rem;
            }

            .value-card {
                border: 1px solid var(--border);
                border-radius: 14px;
                background: #fff;
                padding: 1rem;
                box-shadow: 0 6px 18px rgba(0, 0, 0, 0.05);
            }

            .value-card h4 {
                margin: 0 0 0.35rem 0;
                font-size: 1.05rem;
            }

            .value-card p {
                margin: 0;
                color: var(--muted);
                font-size: 0.92rem;
            }

            .block {
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 1rem 1rem 0.5rem;
                background: var(--surface);
                box-shadow: 0 6px 20px rgba(24, 24, 27, 0.06);
                margin-bottom: 0.9rem;
            }

            .meta {
                color: var(--muted);
                font-size: 0.92rem;
            }

            .source-chip {
                display: inline-block;
                margin: 0.15rem 0.25rem 0.15rem 0;
                padding: 0.2rem 0.5rem;
                border: 1px solid #93c5fd;
                border-radius: 999px;
                background: var(--brand-soft);
                font-size: 0.85rem;
                color: #0b1f44;
                font-weight: 700;
            }

            div[data-testid="stMetric"] {
                background: #ffffff;
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 0.4rem 0.6rem;
            }

            div[data-testid="stMetricLabel"] p,
            div[data-testid="stMetricValue"] {
                color: #000 !important;
            }

            .stButton > button,
            .stDownloadButton > button {
                background: linear-gradient(135deg, var(--brand), #3b82f6) !important;
                color: #fff !important;
                border: 0 !important;
                font-weight: 700 !important;
                border-radius: 10px !important;
                transition: transform .15s ease, box-shadow .15s ease;
                box-shadow: 0 6px 14px rgba(11, 99, 246, 0.28);
            }

            .stButton > button:hover,
            .stDownloadButton > button:hover {
                transform: translateY(-1px);
                box-shadow: 0 10px 18px rgba(11, 99, 246, 0.32);
            }

            div[data-baseweb="input"] input,
            div[data-baseweb="textarea"] textarea {
                color: #000 !important;
                background: #fff !important;
            }

            div[data-baseweb="slider"] * {
                color: #000 !important;
            }

            @media (max-width: 900px) {
                .hero h1 {
                    font-size: 1.55rem;
                }

                .landing-hero h1 {
                    font-size: 1.7rem;
                }

                .kpi-strip,
                .value-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def get_inngest_client() -> inngest.Inngest:
    return inngest.Inngest(app_id="rag_app", is_production=False)


def _init_state() -> None:
    defaults = {
        "qa_history": [],
        "ingested_count": 0,
        "last_source": "-",
        "show_ingestion": False,
        "show_qa": False,
        "inngest_api_base": os.getenv("INNGEST_API_BASE", "http://127.0.0.1:8288/v1"),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _extract_event_id(send_result: Any) -> str:
    if isinstance(send_result, list) and send_result:
        return str(send_result[0])
    if isinstance(send_result, dict):
        ids = send_result.get("ids")
        if isinstance(ids, list) and ids:
            return str(ids[0])
    ids_attr = getattr(send_result, "ids", None)
    if isinstance(ids_attr, list) and ids_attr:
        return str(ids_attr[0])
    raise RuntimeError(f"Could not extract event id from send result: {send_result!r}")


def _missing_env_vars() -> list[str]:
    required = ["GEMINI_API_KEY", "QDRANT_ENDPOINT", "QDRANT_API_KEY"]
    return [name for name in required if not os.getenv(name)]


def _inngest_api_base() -> str:
    return st.session_state.get("inngest_api_base", "http://127.0.0.1:8288/v1").rstrip("/")


def _save_uploaded_pdf(file) -> Path:
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.name).name
    unique_name = f"{int(time.time())}-{safe_name}"
    file_path = uploads_dir / unique_name
    file_path.write_bytes(file.getbuffer())
    return file_path


async def _send_ingest_event(pdf_path: Path, source_id: str) -> None:
    client = get_inngest_client()
    await client.send(
        inngest.Event(
            name="ingest_pdf",
            data={
                "pdf_path": str(pdf_path.resolve()),
                "source_id": source_id,
            },
        )
    )


async def _send_query_event(question: str, top_k: int) -> str:
    client = get_inngest_client()
    send_result = await client.send(
        inngest.Event(
            name="query_pdf",
            data={
                "question": question,
                "top_k": top_k,
            },
        )
    )
    return _extract_event_id(send_result)


def _fetch_runs(event_id: str) -> list[dict]:
    url = f"{_inngest_api_base()}/events/{event_id}/runs"
    response = requests.get(url, timeout=12)
    response.raise_for_status()
    data = response.json()
    return data.get("data", [])


def _wait_for_run_output(event_id: str, timeout_s: float, poll_interval_s: float) -> dict:
    start = time.time()
    last_status = None

    while True:
        runs = _fetch_runs(event_id)
        if runs:
            run = runs[0]
            status = (run.get("status") or "").strip()
            last_status = status or last_status
            normalized = status.lower()

            if normalized in {"completed", "succeeded", "success", "finished"}:
                output = run.get("output")
                if isinstance(output, dict):
                    return output
                if isinstance(output, str) and output.strip():
                    try:
                        parsed = json.loads(output)
                        if isinstance(parsed, dict):
                            return parsed
                    except Exception:
                        pass
                return {}

            if normalized in {"failed", "cancelled"}:
                raise RuntimeError(f"Function run {status}")

        if time.time() - start > timeout_s:
            raise TimeoutError(f"Timed out waiting for output (last status: {last_status})")
        time.sleep(poll_interval_s)


def _check_inngest_connectivity() -> tuple[bool, str]:
    base = _inngest_api_base()
    probes = [f"{base}/health", f"{base}/events"]
    for url in probes:
        try:
            response = requests.get(url, timeout=4)
            if response.status_code < 500:
                return True, f"Reachable: {url} (HTTP {response.status_code})"
        except requests.RequestException:
            continue
    return False, f"Unable to reach Inngest API at {base}"


def _render_sources(sources: list[str]) -> None:
    if not sources:
        return
    chips = "".join(f"<span class='source-chip'>{s}</span>" for s in sources)
    st.markdown(chips, unsafe_allow_html=True)


_init_state()
_inject_styles()

st.markdown(
    """
    <div class="hero">
      <h1>RAG Operations Console</h1>
      <p>Ingest PDF knowledge and query grounded answers with event-driven workflows.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("Runtime Controls")
    if st.button("Document Ingestion", use_container_width=True):
        if st.session_state.show_ingestion:
            st.session_state.show_ingestion = False
        else:
            st.session_state.show_ingestion = True
            st.session_state.show_qa = False
    if st.button("Question Answering", use_container_width=True):
        if st.session_state.show_qa:
            st.session_state.show_qa = False
        else:
            st.session_state.show_qa = True
            st.session_state.show_ingestion = False

    
    st.session_state.inngest_api_base = st.text_input("Inngest API Base", value=st.session_state.inngest_api_base)

    if st.button("Check Inngest Connectivity", use_container_width=True):
        ok, message = _check_inngest_connectivity()
        if ok:
            st.success(message)
        else:
            st.error(message)

    missing = _missing_env_vars()
    if missing:
        st.warning("Missing env vars: " + ", ".join(missing))
    else:
        st.success("Environment variables loaded")

    st.divider()
    st.metric("Ingested (session)", st.session_state.ingested_count)
    st.caption(f"Last source: {st.session_state.last_source}")

show_ingestion = st.session_state.show_ingestion
show_qa = st.session_state.show_qa

if not show_ingestion and not show_qa:
    st.markdown(
        """
        <div class='landing-hero'>
            <span class='landing-pill'>ENTERPRISE AI PLATFORM</span>
            <h1>Turn Documents Into Trusted Decisions</h1>
            <p>
                We help teams operationalize knowledge with production-grade retrieval and grounded AI responses.
                Move from scattered PDFs to a reliable intelligence layer for support, operations, compliance, and leadership.
            </p>
        </div>

        <div class='kpi-strip'>
            <div class='kpi'>
                <h3>Grounded Answers</h3>
                <p>Every response is linked to retrieved source context.</p>
            </div>
            <div class='kpi'>
                <h3>Event-Driven Reliability</h3>
                <p>Workflow execution is traceable, observable, and resilient.</p>
            </div>
            <div class='kpi'>
                <h3>Fast Knowledge Ops</h3>
                <p>Ingest documents and enable searchable intelligence in minutes.</p>
            </div>
        </div>

        <div class='value-grid'>
            <div class='value-card'>
                <h4>Built for Scale</h4>
                <p>Vector-native retrieval and modular services designed for real workloads, not demos.</p>
            </div>
            <div class='value-card'>
                <h4>Security-Aware by Design</h4>
                <p>Environment-based configuration and clean separation between app, storage, and model providers.</p>
            </div>
            <div class='value-card'>
                <h4>Operator-Friendly Console</h4>
                <p>Use the sidebar buttons to launch either ingestion or Q&A workflows instantly.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    if show_ingestion and show_qa:
        col_ingest, col_query = st.columns([1, 1], gap="large")
    elif show_ingestion:
        col_ingest, col_query = st.columns([1, 0.001], gap="small")
    else:
        col_ingest, col_query = st.columns([0.001, 1], gap="small")

    if show_ingestion:
        with col_ingest:
            st.subheader("Document Ingestion")
            uploaded = st.file_uploader("Upload PDF", type=["pdf"], accept_multiple_files=False)
            source_id = st.text_input("Source ID (optional)", placeholder="policy-v3.pdf")

            ingest_disabled = uploaded is None
            if st.button("Ingest Document", type="primary", disabled=ingest_disabled, use_container_width=True):
                try:
                    with st.spinner("Saving file and triggering ingestion event..."):
                        file_path = _save_uploaded_pdf(uploaded)
                        final_source_id = source_id.strip() or uploaded.name
                        _run_async(_send_ingest_event(file_path, final_source_id))

                    st.session_state.ingested_count += 1
                    st.session_state.last_source = final_source_id
                    st.success(f"Ingestion event sent for {final_source_id}")
                    st.caption(f"Stored at: {file_path}")
                except Exception as exc:
                    st.error(f"Ingestion failed: {exc}")

    if show_qa:
        with col_query:
            st.subheader("Question Answering")

            with st.form("rag_query_form", clear_on_submit=False):
                question = st.text_area("Question", placeholder="Ask a question about your ingested PDFs...", height=110)
                top_k = st.slider("Top-K chunks", min_value=1, max_value=20, value=5)
                submitted = st.form_submit_button("Run Retrieval + Answer", type="primary", use_container_width=True)

            if submitted:
                if not question.strip():
                    st.error("Please enter a question.")
                else:
                    try:
                        with st.spinner("Triggering query workflow and waiting for result..."):
                            event_id = _run_async(_send_query_event(question.strip(), int(top_k)))
                            output = _wait_for_run_output(
                                event_id,
                                timeout_s=120.0,
                                poll_interval_s=0.5,
                            )

                        answer = str(output.get("answer", "")).strip()
                        sources = output.get("sources") or []
                        if not isinstance(sources, list):
                            sources = []
                        num_contexts = output.get("num_contexts", "-")
                        timestamp = output.get("timestamp", "-")

                        st.markdown("### Answer")
                        st.write(answer or "(No answer returned)")
                        _render_sources(sources)
                        st.markdown(
                            f"<p class='meta'>Contexts used: {num_contexts} | Timestamp: {timestamp}</p>",
                            unsafe_allow_html=True,
                        )

                        st.session_state.qa_history.insert(
                            0,
                            {
                                "question": question.strip(),
                                "answer": answer,
                                "sources": sources,
                                "num_contexts": num_contexts,
                                "timestamp": timestamp,
                            },
                        )
                        st.session_state.qa_history = st.session_state.qa_history[:10]
                    except Exception as exc:
                        st.error(f"Query failed: {exc}")

        st.markdown("<div class='block'>", unsafe_allow_html=True)
        st.subheader("Recent Query History")

        history = st.session_state.qa_history
        if not history:
            st.caption("No queries yet in this session.")
        else:
            for idx, entry in enumerate(history, start=1):
                with st.expander(f"{idx}. {entry['question'][:85]}"):
                    st.write(entry.get("answer") or "(No answer)")
                    _render_sources(entry.get("sources") or [])
                    st.caption(
                        f"Contexts: {entry.get('num_contexts', '-')} | Timestamp: {entry.get('timestamp', '-')}")

        if st.button("Clear Query History"):
            st.session_state.qa_history = []
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
