# NovaGuard AI

- Setup docker and test

```
docker-compose up -d postgres_db zookeeper kafka ollama
```

Kiểm tra logs của chúng để đảm bảo không có lỗi:

```
docker-compose logs postgres_db
docker-compose logs kafka
docker-compose logs ollama
```

Tải ollama model

```
docker-compose exec ollama ollama pull codellama:7b-instruct-q4_K_M
```