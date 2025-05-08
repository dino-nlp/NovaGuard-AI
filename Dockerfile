# NOVAGUARD-AI/Dockerfile

# ---- Base Image ----
# Sử dụng image Python 3.11 slim làm cơ sở - nhẹ và đủ dùng
FROM python:3.11-slim

# ---- Metadata (Optional) ----
LABEL maintainer="Your Name/Organization <your.email@example.com>" \
      description="NovaGuard AI - Intelligent Code Review Co-Pilot using local LLMs."

# ---- Environment Variables ----
ENV PYTHONUNBUFFERED=1 \
    # Đảm bảo output của Python (print, log) xuất hiện ngay lập tức
    PIP_NO_CACHE_DIR=off \
    # Có thể bật/tắt cache của pip trong quá trình build image
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    # Tắt cảnh báo phiên bản pip
    PIP_DEFAULT_TIMEOUT=100
    # Tăng timeout mặc định cho pip (hữu ích nếu mạng chậm)

# ---- Working Directory ----
WORKDIR /app

# ---- System Dependencies ----
# Cài đặt các gói hệ thống cần thiết
# - git: Cần thiết nếu action cần thao tác git, hoặc để debug trong container
# - build-essential: Chứa các công cụ build C/C++ cần cho việc cài một số gói Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    # ---> Thêm các gói OS khác tại đây nếu cần (ví dụ: curl, jq, openjdk-11-jre-headless cho checkstyle, nodejs và npm cho eslint)
    && rm -rf /var/lib/apt/lists/*

# ---- Install CLI Tools ---
# Cài đặt các công cụ CLI mà ToolRunner sẽ sử dụng, dựa trên cấu hình tools.yml mặc định
# Đảm bảo các phiên bản phù hợp hoặc bỏ ghim version nếu muốn bản mới nhất
# Thêm các tool khác và phụ thuộc của chúng (Node.js, Java...) nếu cần
RUN python -m pip install --upgrade pip \
    && echo "Installing CLI tools: semgrep, pylint..." \
    && python -m pip install --no-cache-dir \
        semgrep \
        pylint
# Ví dụ cài ESLint (Yêu cầu cài Node.js ở bước System Dependencies trước):
# RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*
# RUN npm install -g eslint eslint-plugin-import ... (các plugin cần thiết)

# ---- Install Python Dependencies ----
# Copy file requirements.txt trước để tận dụng Docker layer caching
COPY requirements.txt .
# Cài đặt các thư viện Python
RUN echo "Installing Python requirements..." \
    && python -m pip install --no-cache-dir -r requirements.txt

# ---- Copy Application Code ----
# Copy mã nguồn của action và các file cấu hình
COPY src/ /app/src/
COPY config/ /app/config/
# Copy file entrypoint chính
COPY src/action_entrypoint.py /app/action_entrypoint.py

# ---- User (Optional Best Practice) ----
# Chạy với user không phải root để tăng cường bảo mật (có thể cần điều chỉnh quyền truy cập GITHUB_WORKSPACE)
# RUN useradd --create-home --shell /bin/bash appuser
# USER appuser
# WORKDIR /home/appuser/app 
# RUN chown -R appuser:appuser /app # Cấp quyền cho thư mục app nếu dùng user mới

# ---- Entrypoint ----
# Định nghĩa lệnh sẽ chạy khi container khởi động
# ENTRYPOINT ["python", "-m", "src.action_entrypoint"] 
ENTRYPOINT ["sh", "-c", "echo '--- DEBUG INFO ---'; pwd; ls -la /app; ls -la /app/src; echo '--- Python Path ---'; python -c 'import sys; print(sys.path)'; echo '--- Trying python -m ---'; python -m src.action_entrypoint"]