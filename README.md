# NovaGuard AI

### Setup env

- Cài đặt các docker image cần thiết

```bash
docker-compose up -d postgres_db zookeeper kafka ollama
```

- Kiểm tra logs của chúng để đảm bảo không có lỗi:

```bash
docker-compose logs postgres_db
docker-compose logs kafka
docker-compose logs ollama
```

- Tải ollama model

```bash
docker-compose exec ollama ollama pull codellama:7b-instruct-q4_K_M
```

- Khởi tạo database

```bash
cat novaguard-backend/database/schema.sql | docker-compose exec -T postgres_db psql -U novaguard_user -d novaguard_db
```

- Run backend

```bash
docker-compose up -d --build novaguard_backend_api
# Hoặc nếu muốn rebuild tất cả và chạy:
# docker-compose up -d --build
```

Test APIs tại: http://localhost:8000/docs

- Xóa DB cũ để chạy lại sau khi có thay đổi

```bash
# Kết nối vào psql trong container
docker-compose exec postgres_db psql -U novaguard_user -d novaguard_db
# Bên trong psql:
DROP TABLE IF EXISTS "AnalysisFindings" CASCADE;
DROP TABLE IF EXISTS "PRAnalysisRequests" CASCADE;
DROP TABLE IF EXISTS "Projects" CASCADE;
DROP TABLE IF EXISTS "Users" CASCADE;
\q 
# Sau đó, áp dụng lại schema
cat novaguard-backend/database/schema.sql | docker-compose exec -T postgres_db psql -U novaguard_user -d novaguard_db
```