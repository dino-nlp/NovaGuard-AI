#!/bin/bash

# --- Configuration ---
IMAGE_NAME="novaguard-ai-local-test"
OLLAMA_HOST_URL="http://172.17.0.1:11434"
# OLLAMA_HOST_URL="http://host.docker.internal:11434"
SOURCE_REPO_DIR="./test_repo" # Repo gốc trên host
EVENT_JSON_FILE="./event.json"
INPUT_SARIF_FILENAME="local-novaguard-report.sarif"

# --- Lấy thông tin cần thiết từ event.json ---
# Đảm bảo bạn đã cài jq: sudo apt-get install jq / brew install jq
if ! command -v jq &> /dev/null; then
    echo "Error: jq is not installed. Please install it to parse event.json."
    exit 1
fi
if [ ! -f "$EVENT_JSON_FILE" ]; then
    echo "Error: Event file '$EVENT_JSON_FILE' not found."
    exit 1
fi

HEAD_SHA=$(jq -r '.pull_request.head.sha // ""' "$EVENT_JSON_FILE")
BASE_SHA=$(jq -r '.pull_request.base.sha // ""' "$EVENT_JSON_FILE")
BASE_REF=$(jq -r '.pull_request.base.ref // "main"' "$EVENT_JSON_FILE")
HEAD_REF=$(jq -r '.pull_request.head.ref // "feature"' "$EVENT_JSON_FILE")
REPO_FULL_NAME=$(jq -r '.repository.full_name // "test-user/test-repo"' "$EVENT_JSON_FILE")

# Kiểm tra các SHA lấy được (phải khớp với history trong test_repo)
if [ -z "$HEAD_SHA" ] || [ -z "$BASE_SHA" ]; then
    echo "Error: Could not extract HEAD_SHA or BASE_SHA from $EVENT_JSON_FILE."
    echo "Please ensure $EVENT_JSON_FILE is valid and contains .pull_request.head.sha and .pull_request.base.sha"
    exit 1
fi

echo "--- Using HEAD_SHA: $HEAD_SHA ---"
echo "--- Using BASE_SHA: $BASE_SHA ---"

# --- Script Logic ---
set -e 

# Tạo thư mục clone tạm thời
CLONE_DIR=$(mktemp -d) 
echo "--- Created temporary clone directory: $CLONE_DIR ---"

# Hàm dọn dẹp
cleanup() {
    echo "--- Cleaning up temporary clone directory: $CLONE_DIR ---"
    # Dùng sudo nếu người dùng chạy script không có quyền xóa thư mục tạm
    # rm -rf "$CLONE_DIR" 
    # An toàn hơn là để hệ thống tự dọn /tmp hoặc người dùng tự xóa
}
# Đăng ký hàm cleanup để chạy khi script kết thúc (thành công hoặc lỗi)
trap cleanup EXIT

# 1. Copy nội dung repo nguồn vào thư mục tạm
echo "--- Copying $SOURCE_REPO_DIR content to $CLONE_DIR ---"
# Dùng rsync hoặc cp -a để đảm bảo copy cả thư mục .git
rsync -a "$SOURCE_REPO_DIR/" "$CLONE_DIR/" || cp -a "$SOURCE_REPO_DIR/." "$CLONE_DIR/"
if [ ! -d "$CLONE_DIR/.git" ]; then
    echo "Error: Failed to copy .git directory to $CLONE_DIR. Ensure source repo is valid."
    exit 1
fi
echo "--- Repository content copied ---"

# 2. Chuẩn bị trạng thái Git trong thư mục tạm
echo "--- Preparing Git state in $CLONE_DIR ---"
( # Chạy lệnh git trong subshell để không thay đổi thư mục hiện tại của script chính
  cd "$CLONE_DIR" && \
  git config --global --add safe.directory "$CLONE_DIR" && \
  echo "Current branch before checkout:" && git branch && \
  echo "Checking out HEAD SHA: $HEAD_SHA..." && \
  git checkout "$HEAD_SHA" && \
  echo "Checkout successful. HEAD is now at $HEAD_SHA." && \
  echo "Verifying BASE SHA $BASE_SHA exists..." && \
  git cat-file -e "$BASE_SHA" && \
  echo "BASE SHA $BASE_SHA verified."
) || { echo "Error: Failed to prepare Git state in $CLONE_DIR."; exit 1; } # Thoát nếu có lỗi
echo "--- Git state prepared ---"


# --- Build Docker Image ---
echo "--- Building Docker Image: $IMAGE_NAME ---"
docker build -t $IMAGE_NAME .
echo "--- Docker Image Built ---"


# --- Running Docker Container ---
echo "--- Running NovaGuard AI Action Container ---"

# Biến môi trường cho container (mô phỏng GitHub Actions)
# Lưu ý GITHUB_WORKSPACE và GITHUB_EVENT_PATH là đường dẫn BÊN TRONG container
docker run --rm \
-e INPUT_OLLAMA_BASE_URL="$OLLAMA_HOST_URL" \
-e INPUT_GITHUB_TOKEN="dummy-local-token" \
-e INPUT_SARIF_OUTPUT_FILE="$INPUT_SARIF_FILENAME" \
-e INPUT_FAIL_ON_SEVERITY="warning" \
-e GITHUB_WORKSPACE="/github/workspace" \
-e GITHUB_EVENT_PATH="/github/workflow/event.json" \
-e GITHUB_REPOSITORY="$REPO_FULL_NAME" \
-e GITHUB_SHA="$HEAD_SHA" \
-e GITHUB_BASE_REF="$BASE_REF" \
-e GITHUB_HEAD_REF="$HEAD_REF" \
-e GITHUB_EVENT_NAME="pull_request" \
-e NOVAGUARD_ACTIVE_MODE="test" \
-v "$CLONE_DIR:/github/workspace:rw" \
-v "$(pwd)/$EVENT_JSON_FILE:/github/workflow/event.json:ro" "$IMAGE_NAME" 

echo "--- Container Finished ---"

# --- Check Output ---
# Đường dẫn file SARIF bây giờ nằm trong thư mục clone tạm
OUTPUT_SARIF_PATH="$CLONE_DIR/$INPUT_SARIF_FILENAME" 
echo "--- Checking for SARIF Output at $OUTPUT_SARIF_PATH ---"
if [ -f "$OUTPUT_SARIF_PATH" ]; then
  echo "Success! SARIF report generated at: $OUTPUT_SARIF_PATH"
  echo "You can inspect the file for results."
  # Tùy chọn: Copy file SARIF ra ngoài thư mục output cố định trước khi cleanup
  mkdir -p "./local_output" 
  cp "$OUTPUT_SARIF_PATH" "./local_output/${INPUT_SARIF_FILENAME}_$(date +%s)"
  echo "Copied report to ./local_output/"
else
  echo "Error: SARIF report was not found at $OUTPUT_SARIF_PATH"
  echo "Contents of $CLONE_DIR:"
  ls -la "$CLONE_DIR"
  # exit 1 # Bỏ exit 1 ở đây để trap cleanup vẫn chạy
  # Thay vào đó set exit code cho script
  FINAL_EXIT_CODE=1 
fi

echo "--- Local E2E Test Run Completed ---"
# Cleanup sẽ tự chạy do 'trap cleanup EXIT'
exit ${FINAL_EXIT_CODE:-0} # Thoát với code 0 nếu không có lỗi, 1 nếu có lỗi