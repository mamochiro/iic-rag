import streamlit as st
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

st.set_page_config(page_title="Robowealth Knowledge Base", page_icon="🧠", layout="wide")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🧠 Knowledge Base")
    st.caption("Powered by Confluence · Jira · GitLab")

    st.divider()

    # Sync status
    st.subheader("Sync Status")
    try:
        resp = httpx.get(f"{API_URL}/status", headers={"X-API-Key": API_KEY}, timeout=5)
        for s in resp.json():
            synced = s["last_synced_at"][:16].replace("T", " ")
            st.markdown(f"**{s['source']}** `{s['key']}`  \n🕐 {synced} · {s['chunks']} chunks")
    except Exception:
        st.warning("API offline")

    st.divider()

    # Chunk counts
    st.subheader("Indexed Content")
    try:
        resp = httpx.get(f"{API_URL}/chunks/count", headers={"X-API-Key": API_KEY}, timeout=5)
        counts = resp.json()
        total = sum(counts.values())
        for source, count in counts.items():
            icon = {"confluence": "📄", "jira": "🎫", "gitlab": "🦊"}.get(source, "📦")
            st.markdown(f"{icon} **{source}** — {count} chunks")
        st.metric("Total", total)
    except Exception:
        pass

    st.divider()
    show_rewritten = st.toggle("Show rewritten query", value=False)
    top_k = st.slider("Chunks to retrieve (top-k)", 3, 10, 5)

# ---------------------------------------------------------------------------
# Main chat
# ---------------------------------------------------------------------------
st.title("Ask anything")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Render history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("sources"):
            with st.expander("Sources", expanded=False):
                for r in msg["sources"]:
                    icon = "🦊" if "git.robo" in r["url"] else "🎫" if "browse" in r["url"] else "📄"
                    st.markdown(f"{icon} [{r['title']}]({r['url']}) `{r['score']:.3f}`")
            if show_rewritten and msg.get("rewritten"):
                queries = msg["rewritten"] if isinstance(msg["rewritten"], list) else [msg["rewritten"]]
                extras = [q for q in queries if q != msg.get("question", "")]
                if extras:
                    st.caption("🔁 Also searched: " + " · ".join(f"_{q}_" for q in extras))

# Input
if question := st.chat_input("Ask a question about IIC Portal, code, or Jira issues..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching..."):
            try:
                resp = httpx.post(
                    f"{API_URL}/query",
                    headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
                    json={"question": question, "top_k": top_k},
                    timeout=180,
                )
                data = resp.json()
                answer = data["answer"]
                sources = data.get("retrieved", [])
                rewritten = data.get("rewritten", question)

                st.markdown(answer)

                if sources:
                    with st.expander("Sources", expanded=True):
                        for r in sources:
                            icon = "🦊" if "git.robo" in r["url"] else "🎫" if "browse" in r["url"] else "📄"
                            st.markdown(f"{icon} [{r['title']}]({r['url']}) `{r['score']:.3f}`")

                if show_rewritten and rewritten:
                    queries = rewritten if isinstance(rewritten, list) else [rewritten]
                    extras = [q for q in queries if q != question]
                    if extras:
                        st.caption("🔁 Also searched: " + " · ".join(f"_{q}_" for q in extras))

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "rewritten": rewritten,
                })

            except Exception as e:
                err = f"Error: {e}"
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": err})
