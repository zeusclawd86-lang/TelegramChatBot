"""
Streamlit test for conversational agent.
Simple chat interface to test prompts and LLM responses without Telegram.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st
from dotenv import load_dotenv

from core.config import get_config
from core.orchestrator import ChatOrchestrator

# Load environment variables
load_dotenv(dotenv_path=REPO_ROOT / ".env")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Page config
st.set_page_config(
    page_title="Chat Test",
    page_icon="💬",
    layout="wide"
)

st.title("💬 Conversational Agent Test")
st.markdown("Test the LLM conversation agent without Telegram integration.")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_id" not in st.session_state:
    st.session_state.user_id = 999  # Fixed test user ID

if "orchestrator" not in st.session_state:
    try:
        config = get_config()
        st.session_state.orchestrator = ChatOrchestrator(
            llm_api_key=config.LLM_API_KEY,
            model_name=config.LLM_MODEL_NAME,
            base_url=config.LLM_BASE_URL,
            replicate_api_token=config.REPLICATE_API_TOKEN,
        )
        st.success("✅ Orchestrator initialized")
    except Exception as e:
        st.error(f"❌ Failed to initialize orchestrator: {e}")
        st.stop()

# Sidebar: Context info
with st.sidebar:
    st.header("📊 Context")
    ctx = st.session_state.orchestrator.get_user_context(st.session_state.user_id)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Energy", f"{ctx.energy} ⚡")
    with col2:
        st.metric("Messages", ctx.msg_count)

    st.subheader("Character")
    st.text(ctx.character or "Not set")

    st.subheader("Scenario")
    st.text(ctx.scenario or "Not set")

    st.subheader("Mood")
    st.text(ctx.mood or "Not set")

    st.subheader("Clothes")
    st.text(ctx.clothes or "Not set")

    st.subheader("Location")
    st.text(ctx.location or "Not set")

    st.divider()

    # Quick setup buttons
    st.subheader("Quick Setup")
    if st.button("Default Setup (Blond - Beach)"):
        ctx.character = "Ana — Extrovertida, juguetona y luminosa"
        ctx.physical_description = "blonde hair, blue eyes, white skin"
        ctx.scenario = "Atardecer en la playa — Relajado, cálido y con charla íntima"
        ctx.clothes = "Ropa Normal"
        ctx.location = "Playa Privada"
        ctx.mood = "Normal"
        ctx.is_setup_complete = True
        st.rerun()

    if st.button("Reset Context"):
        st.session_state.orchestrator.ctx_manager.reset_context(st.session_state.user_id)
        st.session_state.messages = []
        st.rerun()

# Main chat area
st.divider()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Type your message..."):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get bot response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            async def get_response():
                response = await st.session_state.orchestrator.process_user_message(
                    st.session_state.user_id,
                    prompt
                )
                return response
            
            response = asyncio.run(get_response())

        if response.no_energy:
            st.warning("⚠️ No energy remaining. Reset context to get more.")
        elif response.text == "SETUP_REQUIRED":
            st.info("📌 Please complete setup (use Default Setup button in sidebar).")
        else:
            st.markdown(response.text)

            # Show debug info in expander
            with st.expander("🔍 Debug Info"):
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Energy After", f"{st.session_state.orchestrator.get_user_context(st.session_state.user_id).energy} ⚡")
                with col2:
                    st.metric("Message Count", st.session_state.orchestrator.get_user_context(st.session_state.user_id).msg_count)

                st.info("📝 Image prompts are now generated dynamically by the image_prompt_agent based on conversation context.")
                
                # Mostrar el último prompt generado si existe
                if st.session_state.user_id in st.session_state.orchestrator.last_prompts:
                    st.text_area(
                        "Last Generated Image Prompt",
                        st.session_state.orchestrator.last_prompts[st.session_state.user_id],
                        height=100
                    )

    st.session_state.messages.append({"role": "assistant", "content": response.text})

# Footer
st.divider()
st.caption("This is a test tool for development. No images are generated in this mode.")