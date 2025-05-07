# NOVAGUARD-AI/Dockerfile
# Base Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install git (cần thiết để lấy diff) và các build tools cơ bản
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# (Tùy chọn) Cài đặt các tool CLI toàn cục nếu cần và không cài qua pip
# Ví dụ: Semgrep (có thể cài qua pip hoặc binary)
# RUN python -m pip install semgrep

# Cài đặt các linter (ví dụ). Cân nhắc cài trong môi trường ảo nếu phức tạp
# RUN npm install -g eslint # Nếu cần eslint cho JavaScript/TypeScript
# RUN apt-get install -y default-jdk && # Ví dụ cho Checkstyle (Java)
#     # Download và cài Checkstyle... (logic phức tạp hơn)

# Copy requirements file và cài đặt Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code và configuration
COPY src/ /app/src/
COPY config/ /app/config/
COPY src/action_entrypoint.py /app/action_entrypoint.py

# Set the entrypoint for the action
ENTRYPOINT ["python", "/app/action_entrypoint.py"]