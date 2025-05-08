# test_direct_stream.py
import ollama
import os
import sys

# Thêm thư mục gốc vào path nếu cần để tìm các cài đặt (mặc dù không cần cho test này)
# project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# sys.path.insert(0, project_root)

TEST_OLLAMA_BASE_URL = os.environ.get("TEST_OLLAMA_BASE_URL", "http://localhost:11434")
# Sử dụng model bạn đã thử và biết là có trên server
TEST_MODEL = "phi3:3.8b-mini-4k-instruct-q4_K_M"

print(f"--- Starting Direct Ollama Stream Test ---")
print(f"Model: {TEST_MODEL}")
print(f"URL:   {TEST_OLLAMA_BASE_URL}")
print("Prompt: Write a single sentence about the future of AI.")
print("Expected output: Streamed sentence parts.")
print("--- Output ---")

try:
    client = ollama.Client(host=TEST_OLLAMA_BASE_URL)
    # Kiểm tra xem model có tồn tại không trước khi stream
    try:
        client.show(TEST_MODEL)
        print(f"[INFO] Model '{TEST_MODEL}' found on server.")
    except ollama.ResponseError as e:
        if e.status_code == 404:
            print(f"[ERROR] Model '{TEST_MODEL}' not found on Ollama server. Please pull it.")
            sys.exit(1)
        else:
            print(f"[ERROR] Error checking model status: {e}")
            sys.exit(1)

    # Bắt đầu stream
    stream = client.chat(
        model=TEST_MODEL,
        messages=[{'role': 'user', 'content': 'Write a single sentence about the future of AI.'}],
        stream=True
    )

    received_content = False
    full_response = []
    for chunk in stream:
        # Mỗi chunk là một dictionary, ví dụ:
        # {'model': 'phi3:mini...', 'created_at': '...', 'message': {'role': 'assistant', 'content': 'The'}, 'done': False}
        # Hoặc chunk cuối cùng:
        # {'model': 'phi3:mini...', 'created_at': '...', 'done': True, 'total_duration': ..., 'load_duration': ..., 'prompt_eval_count': ..., 'eval_count': ..., 'eval_duration': ...}
        
        # Lấy phần content từ message
        message_part = chunk.get('message', {})
        content_part = message_part.get('content')

        if content_part:
            print(content_part, end='', flush=True) # In ra ngay lập tức
            received_content = True
            full_response.append(content_part)

    print("\n--- Stream Finished ---") # In một dòng mới sau khi stream xong

    if received_content:
        print(f"Direct streaming via 'ollama' library SUCCESSFUL.")
        print(f"Full response assembled: {''.join(full_response)}")
    else:
        print(f"Direct streaming via 'ollama' library FAILED: No content chunks were received.")

except ImportError:
     print("\n[ERROR] The 'ollama' library is not installed. Run: pip install ollama")
except Exception as e:
    print(f"\n[ERROR] An error occurred during the direct streaming test: {e}")