# novaguard-backend/app/analysis_worker/consumer.py
import json
import logging
import time
from datetime import datetime, timezone # Thêm timezone
from sqlalchemy.orm import Session # Import Session

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from app.core.config import get_settings
from app.core.db import SessionLocal as WorkerSessionLocal # Đổi tên để rõ ràng là của worker
from app.core.security import decrypt_data
from app.models import User, Project, PRAnalysisRequest, PRAnalysisStatus # Import các model cần thiết
from app.webhook_service import crud_pr_analysis # Sử dụng CRUD đã có
from app.common import GitHubAPIClient # Import GitHub client mới

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AnalysisWorker")


def get_db_session() -> Optional[Session]:
    """Tạo và trả về một DB session cho worker."""
    session_local_factory = WorkerSessionLocal # Đã được khởi tạo trong main() của worker
    if not session_local_factory:
        logger.error("Worker DB SessionLocal factory not configured.")
        return None
    db = None
    try:
        db = session_local_factory()
        return db
    except Exception as e:
        logger.exception(f"Failed to create DB session for worker: {e}")
        if db: # Đảm bảo đóng session nếu nó đã được tạo một phần
            db.close()
        return None


async def process_message_logic(message_value: dict, db: Session): # Thêm async vì có gọi hàm async
    """
    Logic chính để xử lý một message từ Kafka, bao gồm gọi GitHub API.
    """
    pr_analysis_request_id = message_value.get("pr_analysis_request_id")
    if not pr_analysis_request_id:
        logger.error("Message missing 'pr_analysis_request_id'. Skipping.")
        return

    logger.info(f"Processing PRAnalysisRequest ID: {pr_analysis_request_id}")

    # 1. Lấy PRAnalysisRequest và Project từ DB
    db_pr_request = crud_pr_analysis.get_pr_analysis_request_by_id(db, pr_analysis_request_id)
    if not db_pr_request:
        logger.error(f"PRAnalysisRequest ID {pr_analysis_request_id} not found in DB. Skipping.")
        return

    if db_pr_request.status not in [PRAnalysisStatus.PENDING, PRAnalysisStatus.FAILED]: # Chỉ xử lý PENDING hoặc FAILED (để retry)
        logger.info(f"PRAnalysisRequest ID {pr_analysis_request_id} is not in PENDING/FAILED state (current: {db_pr_request.status.value}). Skipping.")
        return

    db_project = db.query(Project).filter(Project.id == db_pr_request.project_id).first()
    if not db_project:
        logger.error(f"Project ID {db_pr_request.project_id} for PRAnalysisRequest {pr_analysis_request_id} not found. Marking as FAILED.")
        crud_pr_analysis.update_pr_analysis_request_status(db, pr_analysis_request_id, PRAnalysisStatus.FAILED, "Associated project not found")
        return

    # 2. Cập nhật status thành "processing"
    crud_pr_analysis.update_pr_analysis_request_status(db, pr_analysis_request_id, PRAnalysisStatus.PROCESSING)
    logger.info(f"Updated PRAnalysisRequest {pr_analysis_request_id} status to PROCESSING.")

    # 3. Lấy GitHub Access Token
    user_id_from_message = message_value.get("user_id") # user_id được gửi từ webhook_service
    if not user_id_from_message:
        logger.error(f"user_id missing in Kafka message for PRAnalysisRequest {pr_analysis_request_id}. Marking as FAILED.")
        crud_pr_analysis.update_pr_analysis_request_status(db, pr_analysis_request_id, PRAnalysisStatus.FAILED, "User ID missing in task payload")
        return
        
    db_user = db.query(User).filter(User.id == user_id_from_message).first()
    if not db_user or not db_user.github_access_token_encrypted:
        logger.error(f"User ID {user_id_from_message} not found or GitHub token missing for PRAnalysisRequest {pr_analysis_request_id}. Marking as FAILED.")
        crud_pr_analysis.update_pr_analysis_request_status(db, pr_analysis_request_id, PRAnalysisStatus.FAILED, "User or GitHub token not found")
        return

    github_token = decrypt_data(db_user.github_access_token_encrypted)
    if not github_token:
        logger.error(f"Failed to decrypt GitHub token for user ID {user_id_from_message} (PRAnalysisRequest {pr_analysis_request_id}). Marking as FAILED.")
        crud_pr_analysis.update_pr_analysis_request_status(db, pr_analysis_request_id, PRAnalysisStatus.FAILED, "GitHub token decryption error")
        return
    
    logger.info(f"Successfully decrypted GitHub token for user ID {user_id_from_message}.")
    gh_client = GitHubAPIClient(token=github_token)

    # 4. Gọi GitHub API
    # repo_name là 'owner/repo'
    owner, repo_slug = db_project.repo_name.split('/', 1) if '/' in db_project.repo_name else (None, None)
    if not owner or not repo_slug:
        logger.error(f"Invalid repo_name format: {db_project.repo_name} for project ID {db_project.id}. Marking as FAILED.")
        crud_pr_analysis.update_pr_analysis_request_status(db, pr_analysis_request_id, PRAnalysisStatus.FAILED, "Invalid project repo_name format")
        return

    pr_number = db_pr_request.pr_number
    head_sha_from_message = message_value.get("head_sha") # SHA từ webhook payload

    try:
        logger.info(f"Fetching PR details for {owner}/{repo_slug} PR #{pr_number}...")
        pr_details = await gh_client.get_pull_request_details(owner, repo_slug, pr_number)
        if not pr_details:
            raise Exception("Failed to fetch PR details from GitHub.")
        
        # Cập nhật head_sha từ PR details nếu có, hoặc dùng từ message
        actual_head_sha = pr_details.get("head", {}).get("sha", head_sha_from_message)
        if not actual_head_sha:
             raise Exception("Could not determine head SHA for the PR.")
        
        # Cập nhật lại head_sha và pr_title, pr_github_url trong DB nếu nó thay đổi hoặc chưa có
        if db_pr_request.head_sha != actual_head_sha or \
           db_pr_request.pr_title != pr_details.get("title") or \
           str(db_pr_request.pr_github_url) != pr_details.get("html_url"): # So sánh str với HttpUrl
            db_pr_request.head_sha = actual_head_sha
            db_pr_request.pr_title = pr_details.get("title")
            db_pr_request.pr_github_url = pr_details.get("html_url")
            # Không commit ngay, sẽ commit chung ở cuối hoặc khi xử lý xong
        
        logger.info(f"Fetching PR diff for {owner}/{repo_slug} PR #{pr_number}...")
        pr_diff = await gh_client.get_pull_request_diff(owner, repo_slug, pr_number)
        if pr_diff is None: # Diff có thể là empty string, nhưng không nên là None nếu API thành công
            logger.warning(f"PR diff is None for {owner}/{repo_slug} PR #{pr_number}. Proceeding without diff.")
            pr_diff = "" # Đặt là chuỗi rỗng nếu None

        logger.info(f"Fetching changed files for {owner}/{repo_slug} PR #{pr_number}...")
        changed_files_info = await gh_client.get_pull_request_files(owner, repo_slug, pr_number)
        if changed_files_info is None: # Nên là list rỗng nếu không có file, không phải None
            logger.warning(f"Changed files list is None for {owner}/{repo_slug} PR #{pr_number}. Proceeding without file contents.")
            changed_files_info = []

        changed_files_content: List[Dict[str, Any]] = []
        for file_info in changed_files_info:
            if file_info.get("status") == "removed": # Bỏ qua file bị xóa
                logger.debug(f"Skipping removed file: {file_info['filename']}")
                continue
            
            file_path = file_info["filename"]
            logger.debug(f"Fetching content for file: {file_path} at ref {actual_head_sha}...")
            content = await gh_client.get_file_content(owner, repo_slug, file_path, ref=actual_head_sha)
            changed_files_content.append({
                "filename": file_path,
                "status": file_info.get("status"),
                "patch": file_info.get("patch"), # Patch cho từng file (nếu có)
                "content": content if content is not None else "" # Đảm bảo content là string
            })
        
        logger.info(f"Successfully fetched data for PRAnalysisRequest ID: {pr_analysis_request_id}")
        logger.info(f"  PR Title: {pr_details.get('title')}")
        logger.info(f"  PR Diff (first 200 chars): {pr_diff[:200] if pr_diff else 'N/A'}")
        logger.info(f"  Number of changed files fetched: {len(changed_files_content)}")
        # for f_content in changed_files_content:
        #     logger.debug(f"    File: {f_content['filename']}, Status: {f_content['status']}, Content snippet: {(f_content['content'] or '')[:50]}")

        # ---- Dữ liệu đã sẵn sàng cho Phase 3 (LLM Analysis) ----
        # dynamic_project_context = {
        #     "pr_metadata": pr_details,
        #     "pr_diff": pr_diff,
        #     "changed_files": changed_files_content,
        #     "project_language": db_project.language,
        #     "project_custom_notes": db_project.custom_project_notes,
        #     # Thêm CKG context sau này
        # }
        # Gọi Analysis Orchestrator với dynamic_project_context
        # findings = analysis_orchestrator.run_analysis(dynamic_project_context)
        # crud_analysis_finding.create_findings(db, pr_analysis_request_id, findings)
        
        # Tạm thời cho MVP (Phase 2), sau khi lấy dữ liệu, đánh dấu là COMPLETED (placeholder)
        # Sau này, status COMPLETED chỉ được set sau khi LLM xử lý xong.
        logger.info(f"Placeholder: Data fetching complete for PRAnalysisRequest ID {pr_analysis_request_id}. Marking as COMPLETED (for now).")
        crud_pr_analysis.update_pr_analysis_request_status(db, pr_analysis_request_id, PRAnalysisStatus.COMPLETED)

    except Exception as e:
        error_msg = f"Error processing PRAnalysisRequest {pr_analysis_request_id}: {str(e)}"
        logger.exception(error_msg) # Log full traceback
        try:
            crud_pr_analysis.update_pr_analysis_request_status(db, pr_analysis_request_id, PRAnalysisStatus.FAILED, error_msg[:1000]) # Giới hạn độ dài error message
        except Exception as db_error:
            logger.error(f"Additionally, failed to update PRAnalysisRequest status to FAILED: {db_error}")


async def consume_messages(): # Thêm async để có thể await process_message_logic
    settings_obj = get_settings()
    consumer = None
    
    max_retries = 5; retry_delay = 10
    for attempt in range(max_retries):
        try:
            consumer = KafkaConsumer(
                settings_obj.KAFKA_PR_ANALYSIS_TOPIC,
                bootstrap_servers=settings_obj.KAFKA_BOOTSTRAP_SERVERS.split(','),
                auto_offset_reset='earliest',
                group_id='novaguard-analysis-workers-v2', # Thay đổi group_id nếu logic thay đổi nhiều
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                consumer_timeout_ms=5000 # Thoát vòng lặp nếu không có message sau 5s để có thể shutdown nhẹ nhàng
            )
            logger.info(f"KafkaConsumer connected to {settings_obj.KAFKA_BOOTSTRAP_SERVERS}, topic '{settings_obj.KAFKA_PR_ANALYSIS_TOPIC}'")
            break
        except KafkaError as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries}: Kafka connection failed: {e}. Retrying in {retry_delay}s...")
            if attempt + 1 == max_retries: logger.error("Max retries reached. Exiting."); return
            time.sleep(retry_delay)
    if not consumer: return

    # Khởi tạo WorkerSessionLocal một lần khi worker bắt đầu
    if not WorkerSessionLocal._sessionmaker_configured_warning: # Kiểm tra cờ nội bộ nếu có, hoặc tự set cờ
         WorkerSessionLocal() # Gọi để khởi tạo engine nếu chưa
         logger.info("Worker DB Session factory initialized.")


    logger.info("Analysis worker started. Waiting for messages...")
    try:
        for message in consumer:
            logger.info(f"Consumed: topic={message.topic}, part={message.partition}, offset={message.offset}, key={message.key}, len_val={len(message.value)}")
            db_session = get_db_session()
            if db_session:
                try:
                    await process_message_logic(message.value, db_session) # Await hàm xử lý
                finally:
                    db_session.close()
            else:
                logger.error("Could not get DB session for processing message. Message might be re-processed or lost if not handled.")
                # Cân nhắc đưa message trở lại queue hoặc vào dead-letter queue nếu DB lỗi nghiêm trọng
            
            # Nếu dùng auto_commit_enable=False (mặc định là True), bạn cần commit offset thủ công:
            # consumer.commit()
    except KeyboardInterrupt:
        logger.info("Analysis worker shutting down (KeyboardInterrupt)...")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in consumer loop: {e}")
    finally:
        if consumer:
            consumer.close()
            logger.info("KafkaConsumer closed.")

def main_worker(): # Đổi tên hàm main để chạy bằng python -m
    # Khởi tạo DB session factory cho worker trước khi vào vòng lặp consumer
    # Cách này có thể không hoạt động tốt nếu get_settings() trả về instance đã cache mà không có DATABASE_URL đúng
    # Tốt hơn là WorkerSessionLocal() được gọi trong consume_messages
    # WorkerSessionLocal() 
    
    import asyncio
    asyncio.run(consume_messages())


if __name__ == "__main__":
    main_worker()