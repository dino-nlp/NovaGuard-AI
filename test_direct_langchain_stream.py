# test_direct_langchain_stream.py
import asyncio
import logging
import os
import sys

# Thêm src vào sys.path nếu cần (thường không cần cho test script này)
# project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
log = logging.getLogger(__name__)

try:
    from langchain_ollama.chat_models import ChatOllama
    from langchain_core.messages import HumanMessage
except ImportError:
    log.error("langchain-ollama or langchain-core not installed properly.")
    sys.exit(1)

BASE_URL = os.environ.get("TEST_OLLAMA_BASE_URL", "http://localhost:11434")
MODEL = "phi3:3.8b-mini-4k-instruct-q4_K_M" # Model chúng ta biết là có và stream được bằng ollama lib

async def test_astream():
    log.info(f"\n--- Testing direct ChatOllama.astream with model {MODEL} ---")
    llm = ChatOllama(model=MODEL, base_url=BASE_URL, temperature=0.5)
    messages = [HumanMessage(content="Async stream test: a short sentence about programming.")]
    chunks = []
    received_any = False
    try:
        async for chunk in llm.astream(messages):
            log.info(f"Async Chunk Content: {chunk.content}")
            if chunk.content: # Chỉ thêm nếu có nội dung thực sự
               chunks.append(chunk.content)
               received_any = True
    except Exception as e:
        log.error(f"ERROR during astream: {e}", exc_info=True)
    log.info(f"Async test finished. Received any chunks: {received_any}. Number of non-empty chunks: {len(chunks)}")
    if not received_any: log.warning("!!! Async streaming via langchain-ollama yielded no content chunks.")

def test_stream():
    log.info(f"\n--- Testing direct ChatOllama.stream with model {MODEL} ---")
    llm = ChatOllama(model=MODEL, base_url=BASE_URL, temperature=0.5)
    messages = [HumanMessage(content="Sync stream test: another short sentence about AI.")]
    chunks = []
    received_any = False
    try:
        for chunk in llm.stream(messages):
            log.info(f"Sync Chunk Content: {chunk.content}")
            if chunk.content:
                chunks.append(chunk.content)
                received_any = True
    except Exception as e:
        log.error(f"ERROR during stream: {e}", exc_info=True)
    log.info(f"Sync test finished. Received any chunks: {received_any}. Number of non-empty chunks: {len(chunks)}")
    if not received_any: log.warning("!!! Sync streaming via langchain-ollama yielded no content chunks.")

if __name__ == "__main__":
    test_stream() # Chạy test đồng bộ trước
    asyncio.run(test_astream()) # Chạy test bất đồng bộ