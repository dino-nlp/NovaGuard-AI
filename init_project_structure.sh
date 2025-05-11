#!/bin/bash

# init_project_structure.sh
# Script để khởi tạo cấu trúc thư mục cho dự án NovaGuard-AI.
# Chạy script này từ thư mục gốc của dự án (novaguard-ai).

echo "Đang khởi tạo cấu trúc thư mục cho NovaGuard-AI..."

# Danh sách tất cả các thư mục cần tạo
directories=(
  # Frontend UI
  "novaguard-ui/public"
  "novaguard-ui/src/assets"
  "novaguard-ui/src/components/auth"
  "novaguard-ui/src/components/project"
  "novaguard-ui/src/components/pr"
  "novaguard-ui/src/constants"
  "novaguard-ui/src/contexts"
  "novaguard-ui/src/features/auth"
  "novaguard-ui/src/features/projects"
  "novaguard-ui/src/features/pullRequests"
  "novaguard-ui/src/hooks"
  "novaguard-ui/src/layouts"
  "novaguard-ui/src/pages"
  "novaguard-ui/src/services"
  "novaguard-ui/src/store"
  "novaguard-ui/src/types"
  "novaguard-ui/src/utils"

  # Backend Services
  "novaguard-backend/services/auth_service/app/api/v1"
  "novaguard-backend/services/auth_service/app/core"
  "novaguard-backend/services/auth_service/app/crud"
  "novaguard-backend/services/auth_service/app/db"
  "novaguard-backend/services/auth_service/app/models"
  "novaguard-backend/services/auth_service/app/schemas"
  "novaguard-backend/services/auth_service/app/services" # Business logic services for auth
  "novaguard-backend/services/auth_service/tests"

  "novaguard-backend/services/project_service/app/api/v1"
  "novaguard-backend/services/project_service/app/core"
  "novaguard-backend/services/project_service/app/crud"
  "novaguard-backend/services/project_service/app/db"
  "novaguard-backend/services/project_service/app/models"
  "novaguard-backend/services/project_service/app/schemas"
  "novaguard-backend/services/project_service/app/services" # Business logic services for project
  "novaguard-backend/services/project_service/tests"

  "novaguard-backend/services/webhook_service/app/api/v1"
  "novaguard-backend/services/webhook_service/app/core"
  "novaguard-backend/services/webhook_service/app/schemas" # Pydantic schemas for webhook payloads
  "novaguard-backend/services/webhook_service/app/services" # Business logic services for webhook
  "novaguard-backend/services/webhook_service/tests"

  "novaguard-backend/services/analysis_worker/app/core"
  "novaguard-backend/services/analysis_worker/app/db"
  "novaguard-backend/services/analysis_worker/app/models"
  "novaguard-backend/services/analysis_worker/app/crud"
  "novaguard-backend/services/analysis_worker/app/analysis_orchestrator/agents"
  "novaguard-backend/services/analysis_worker/app/llm_wrapper"
  "novaguard-backend/services/analysis_worker/app/services" # Business logic services for worker
  "novaguard-backend/services/analysis_worker/tests"

  # Common backend code
  "novaguard-backend/common/db_base"
  "novaguard-backend/common/models_shared"
  "novaguard-backend/common/schemas_shared"

  # Documentation
  "docs/api"

  # Scripts
  "scripts"
)

# Tạo các thư mục
for dir in "${directories[@]}"; do
  mkdir -p "$dir"
  echo "Đã tạo thư mục: $dir"
done

# Danh sách các thư mục lá (hoặc thư mục dự kiến ban đầu trống) cần file .gitkeep
gitkeep_dirs=(
  "novaguard-ui/public"
  "novaguard-ui/src/assets"
  "novaguard-ui/src/components/auth"
  "novaguard-ui/src/components/project"
  "novaguard-ui/src/components/pr"
  "novaguard-ui/src/constants"
  "novaguard-ui/src/contexts"
  "novaguard-ui/src/features/auth"
  "novaguard-ui/src/features/projects"
  "novaguard-ui/src/features/pullRequests"
  "novaguard-ui/src/hooks"
  "novaguard-ui/src/layouts"
  "novaguard-ui/src/pages" # Sẽ chứa các file trang sau này
  "novaguard-ui/src/services" # Sẽ chứa các file gọi API sau này
  "novaguard-ui/src/store" # Sẽ chứa cấu hình state management sau này
  "novaguard-ui/src/types" # Sẽ chứa các định nghĩa TypeScript sau này
  "novaguard-ui/src/utils" # Sẽ chứa các hàm tiện ích sau này

  "novaguard-backend/services/auth_service/app/api/v1"
  "novaguard-backend/services/auth_service/app/core"
  "novaguard-backend/services/auth_service/app/crud"
  "novaguard-backend/services/auth_service/app/db"
  "novaguard-backend/services/auth_service/app/models"
  "novaguard-backend/services/auth_service/app/schemas"
  "novaguard-backend/services/auth_service/app/services"
  "novaguard-backend/services/auth_service/tests"

  "novaguard-backend/services/project_service/app/api/v1"
  "novaguard-backend/services/project_service/app/core"
  "novaguard-backend/services/project_service/app/crud"
  "novaguard-backend/services/project_service/app/db"
  "novaguard-backend/services/project_service/app/models"
  "novaguard-backend/services/project_service/app/schemas"
  "novaguard-backend/services/project_service/app/services"
  "novaguard-backend/services/project_service/tests"

  "novaguard-backend/services/webhook_service/app/api/v1"
  "novaguard-backend/services/webhook_service/app/core"
  "novaguard-backend/services/webhook_service/app/schemas"
  "novaguard-backend/services/webhook_service/app/services"
  "novaguard-backend/services/webhook_service/tests"

  "novaguard-backend/services/analysis_worker/app/core"
  "novaguard-backend/services/analysis_worker/app/db"
  "novaguard-backend/services/analysis_worker/app/models"
  "novaguard-backend/services/analysis_worker/app/crud"
  "novaguard-backend/services/analysis_worker/app/analysis_orchestrator/agents"
  "novaguard-backend/services/analysis_worker/app/llm_wrapper"
  "novaguard-backend/services/analysis_worker/app/services"
  "novaguard-backend/services/analysis_worker/tests"

  "novaguard-backend/common/db_base"
  "novaguard-backend/common/models_shared"
  "novaguard-backend/common/schemas_shared"

  "docs/api" # Sẽ chứa file openapi.yaml sau này
  "scripts" # Sẽ chứa các script tiện ích sau này
)

# Tạo file .gitkeep trong các thư mục trống
for gk_dir in "${gitkeep_dirs[@]}"; do
  # Kiểm tra xem thư mục có tồn tại không (mặc dù mkdir -p đã tạo chúng)
  if [ -d "$gk_dir" ]; then
    touch "$gk_dir/.gitkeep"
    echo "Đã tạo .gitkeep trong: $gk_dir"
  else
    echo "Cảnh báo: Thư mục $gk_dir không tồn tại để tạo .gitkeep."
  fi
done

echo "Hoàn tất khởi tạo cấu trúc thư mục."
echo "Bạn có thể cần tạo các file cơ bản như package.json cho 'novaguard-ui' và requirements.txt cho từng backend service."