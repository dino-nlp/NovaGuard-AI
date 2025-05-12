import json
import logging
import time
import os # Để có thể truy cập biến môi trường cho DB URL
from sqlalchemy import create_engine, text # Thêm text
from sqlalchemy.orm import sessionmaker

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from app.core.config import get_settings # Sử dụng get_settings() để load config
# (Sẽ cần import model và crud cho PRAnalysisRequest sau)
# from app.models.pr_analysis_request_model import PRAnalysisRequest # Giả sử có model này
# from app.crud.crud_pr_analysis_request import update_pr_analysis_request_status # Giả sử có hàm này

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnalysisWorkerConsumer")
# ---

# --- Database Setup (Worker cần kết nối DB riêng) ---
# Worker không chạy trong context của FastAPI app, nên cần tự thiết lập DB session
# Điều này có thể được refactor vào một module db_worker_session.py nếu dùng ở nhiều worker
_worker_db_session_local = None

def get_worker_db_session_local():
    global _worker_db_session_local
    if _worker_db_session_local is None:
        settings_obj = get_settings() # Load settings
        try:
            engine = create_engine(settings_obj.DATABASE_URL)
            _worker_db_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            logger.info("Worker DB SessionLocal configured.")
        except Exception as e:
            logger.error(f"Failed to configure Worker DB SessionLocal: {e}")
            # Có thể raise lỗi hoặc thoát nếu DB là bắt buộc để worker chạy
    return _worker_db_session_local

def process_message(message_value: dict, db_session_local):
    logger.info(f"Received message: {message_value}")
    
    pr_analysis_request_id = message_value.get("pr_analysis_request_id")
    project_id = message_value.get("project_id")
    # Các thông tin khác như diff_url, head_sha...
    
    if not pr_analysis_request_id:
        logger.error("Message missing 'pr_analysis_request_id'. Skipping.")
        return

    # TODO MVP1:
    # 1. Lấy một session từ db_session_local
    #    SessionLocal = get_worker_db_session_local()
    #    if not SessionLocal:
    #        logger.error("DB Session not available for worker. Cannot process message.")
    #        return
    #    db = SessionLocal()
    # try:
    #    2. Tìm PRAnalysisRequest trong DB bằng pr_analysis_request_id
    #       (Cần tạo model PRAnalysisRequest và CRUD cho nó trước)
    #       request_obj = db.query(PRAnalysisRequest).filter(PRAnalysisRequest.id == pr_analysis_request_id).first()
    #    3. Nếu tìm thấy, cập nhật status thành "processing" (hoặc "received_from_queue")
    #       if request_obj:
    #           request_obj.status = "processing" # Hoặc một status mới
    #           request_obj.started_at = datetime.utcnow() # Nếu cần
    #           db.commit()
    #           logger.info(f"Updated PRAnalysisRequest {pr_analysis_request_id} status to processing.")
    #
    #           # *** PHẦN LOGIC PHÂN TÍCH CHÍNH SẼ ĐẾN SAU Ở CÁC PHASE TIẾP THEO ***
    #           # Tạm thời, sau khi "xử lý", có thể cập nhật thành "completed" (placeholder)
    #           time.sleep(5) # Giả lập thời gian xử lý
    #           request_obj.status = "completed" # Placeholder
    #           request_obj.completed_at = datetime.utcnow()
    #           db.commit()
    #           logger.info(f"Placeholder processing for {pr_analysis_request_id} completed.")
    #
    #       else:
    #           logger.warning(f"PRAnalysisRequest {pr_analysis_request_id} not found in DB.")
    #
    # except Exception as e:
    #    logger.error(f"Error processing message for {pr_analysis_request_id}: {e}")
    #    if db:
    #        db.rollback()
    # finally:
    #    if db:
    #        db.close()
    pass # Bỏ qua phần DB cho bước đầu này

def main():
    settings_obj = get_settings() # Load settings
    consumer = None
    
    # Vòng lặp để thử kết nối lại nếu Kafka broker chưa sẵn sàng ngay
    max_retries = 5
    retry_delay = 10 # seconds
    for attempt in range(max_retries):
        try:
            consumer = KafkaConsumer(
                settings_obj.KAFKA_PR_ANALYSIS_TOPIC,
                bootstrap_servers=settings_obj.KAFKA_BOOTSTRAP_SERVERS.split(','),
                auto_offset_reset='earliest', # Bắt đầu đọc từ message cũ nhất nếu consumer mới
                group_id='novaguard-analysis-workers', # Tên consumer group
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                # consumer_timeout_ms=1000 # Để consumer không block vô hạn nếu không có message
            )
            logger.info(
                f"KafkaConsumer connected to {settings_obj.KAFKA_BOOTSTRAP_SERVERS}, "
                f"subscribed to topic '{settings_obj.KAFKA_PR_ANALYSIS_TOPIC}'"
            )
            break # Thoát vòng lặp nếu kết nối thành công
        except KafkaError as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries}: Kafka connection failed: {e}. Retrying in {retry_delay}s...")
            if attempt + 1 == max_retries:
                logger.error("Max retries reached. Could not connect to Kafka. Exiting.")
                return # Hoặc exit(1)
            time.sleep(retry_delay)
    
    if not consumer: # Nếu vẫn không kết nối được sau tất cả các lần thử
         return

    # Thiết lập DB session factory cho worker
    WorkerSessionLocal = get_worker_db_session_local()
    if not WorkerSessionLocal:
        logger.error("Failed to initialize DB connection for worker. Worker will run without DB updates.")
        # Quyết định có nên thoát worker ở đây không tùy thuộc vào logic của bạn
        # return # Hoặc exit(1)

    logger.info("Analysis worker started. Waiting for messages...")
    try:
        for message in consumer:
            # message value and key are raw bytes -- decode if necessary!
            # e.g., for unicode: `message.value.decode('utf-8')`
            logger.info(
                f"Consumed message: topic={message.topic}, partition={message.partition}, "
                f"offset={message.offset}, key={message.key}, value_len={len(message.value)}"
            )
            process_message(message.value, WorkerSessionLocal)
            # Commit offset thủ công nếu enable_auto_commit=False (mặc định là True)
            # consumer.commit() 
    except KeyboardInterrupt:
        logger.info("Analysis worker shutting down (KeyboardInterrupt)...")
    except Exception as e:
        logger.error(f"An unexpected error occurred in consumer loop: {e}")
    finally:
        if consumer:
            consumer.close()
            logger.info("KafkaConsumer closed.")

if __name__ == "__main__":
    main()