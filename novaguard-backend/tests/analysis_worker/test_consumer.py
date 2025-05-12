import unittest
from unittest.mock import patch, MagicMock, AsyncMock, ANY
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session # Import Session

# Các đối tượng cần import từ app
from app.models import User, Project, PRAnalysisRequest, PRAnalysisStatus
from app.core.config import get_settings # Dùng get_settings để đảm bảo settings được load
from app.analysis_worker import consumer # Module consumer để test process_message_logic

# Giả lập các module/hàm mà consumer.py sẽ gọi
# mock_db_session sẽ được tạo trong setUp
# mock_gh_client sẽ được tạo khi patch GitHubAPIClient

class TestAnalysisWorkerConsumer(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_db_session = MagicMock(spec=Session)
        self.settings = get_settings() # Lấy settings thật để test

        # Dữ liệu message mẫu từ Kafka
        self.mock_kafka_message_value = {
            "pr_analysis_request_id": 1,
            "project_id": 10,
            "user_id": 100,
            "github_repo_id": "gh_repo_123",
            "pr_number": 5,
            "head_sha": "test_head_sha_from_kafka",
            "diff_url": "http://example.com/diff/5"
        }

        # Mock các đối tượng DB được trả về
        self.mock_db_pr_request = MagicMock(spec=PRAnalysisRequest)
        self.mock_db_pr_request.id = self.mock_kafka_message_value["pr_analysis_request_id"]
        self.mock_db_pr_request.project_id = self.mock_kafka_message_value["project_id"]
        self.mock_db_pr_request.pr_number = self.mock_kafka_message_value["pr_number"]
        self.mock_db_pr_request.status = PRAnalysisStatus.PENDING # Trạng thái ban đầu
        self.mock_db_pr_request.head_sha = None # Giả sử ban đầu chưa có
        self.mock_db_pr_request.pr_title = None
        self.mock_db_pr_request.pr_github_url = None


        self.mock_db_project = MagicMock(spec=Project)
        self.mock_db_project.id = self.mock_kafka_message_value["project_id"]
        self.mock_db_project.repo_name = "testowner/testrepo"
        self.mock_db_project.language = "Python"
        self.mock_db_project.custom_project_notes = "Some notes"

        self.mock_db_user = MagicMock(spec=User)
        self.mock_db_user.id = self.mock_kafka_message_value["user_id"]
        self.mock_db_user.github_access_token_encrypted = "encrypted_gh_token_data"

    @patch("app.analysis_worker.consumer.crud_pr_analysis.get_pr_analysis_request_by_id")
    @patch("app.analysis_worker.consumer.crud_pr_analysis.update_pr_analysis_request_status")
    @patch("app.analysis_worker.consumer.decrypt_data")
    @patch("app.analysis_worker.consumer.GitHubAPIClient") # Patch class GitHubAPIClient
    async def test_process_message_logic_success(
        self, MockGitHubAPIClient: MagicMock, mock_decrypt: MagicMock, 
        mock_update_status: MagicMock, mock_get_pr_req: MagicMock
    ):
        # --- Setup mocks ---
        mock_get_pr_req.return_value = self.mock_db_pr_request
        self.mock_db_session.query(Project).filter().first.return_value = self.mock_db_project
        self.mock_db_session.query(User).filter().first.return_value = self.mock_db_user
        mock_decrypt.return_value = "decrypted_github_token_string"

        # Mock instance của GitHubAPIClient và các phương thức của nó
        mock_gh_client_instance = MockGitHubAPIClient.return_value
        mock_gh_client_instance.get_pull_request_details = AsyncMock(return_value={
            "title": "Test PR Title from GH", "head": {"sha": "new_head_sha_from_gh"}, "html_url": "http://github.com/pr/5"
        })
        mock_gh_client_instance.get_pull_request_diff = AsyncMock(return_value="mocked PR diff content")
        mock_gh_client_instance.get_pull_request_files = AsyncMock(return_value=[
            {"filename": "file1.py", "status": "modified", "patch": "patch_for_file1"},
            {"filename": "file2.py", "status": "added", "patch": "patch_for_file2"},
            {"filename": "file3.py", "status": "removed"}
        ])
        # Giả lập get_file_content trả về nội dung khác nhau cho các file
        async def mock_get_content(owner, repo, file_path, ref):
            if file_path == "file1.py": return "content for file1"
            if file_path == "file2.py": return "content for file2"
            return None
        mock_gh_client_instance.get_file_content = AsyncMock(side_effect=mock_get_content)

        # --- Gọi hàm cần test ---
        await consumer.process_message_logic(self.mock_kafka_message_value, self.mock_db_session)

        # --- Assertions ---
        # 1. Kiểm tra get_pr_analysis_request_by_id được gọi
        mock_get_pr_req.assert_called_once_with(self.mock_db_session, self.mock_kafka_message_value["pr_analysis_request_id"])
        
        # 2. Kiểm tra query Project và User
        self.mock_db_session.query(Project).filter().first.assert_called_once()
        self.mock_db_session.query(User).filter().first.assert_called_once()

        # 3. Kiểm tra update_pr_analysis_request_status được gọi 2 lần (PROCESSING và COMPLETED)
        self.assertEqual(mock_update_status.call_count, 2)
        mock_update_status.assert_any_call(self.mock_db_session, self.mock_db_pr_request.id, PRAnalysisStatus.PROCESSING)
        mock_update_status.assert_any_call(self.mock_db_session, self.mock_db_pr_request.id, PRAnalysisStatus.COMPLETED) # Hiện tại là COMPLETED

        # 4. Kiểm tra decrypt_data được gọi
        mock_decrypt.assert_called_once_with("encrypted_gh_token_data")

        # 5. Kiểm tra GitHubAPIClient được khởi tạo với token đúng
        MockGitHubAPIClient.assert_called_once_with(token="decrypted_github_token_string")

        # 6. Kiểm tra các phương thức của GitHubAPIClient được gọi
        mock_gh_client_instance.get_pull_request_details.assert_called_once()
        mock_gh_client_instance.get_pull_request_diff.assert_called_once()
        mock_gh_client_instance.get_pull_request_files.assert_called_once()
        self.assertEqual(mock_gh_client_instance.get_file_content.call_count, 2) # Chỉ gọi cho file1 và file2

        # 7. Kiểm tra PRAnalysisRequest object có được cập nhật head_sha, title, url không
        self.assertEqual(self.mock_db_pr_request.head_sha, "new_head_sha_from_gh")
        self.assertEqual(self.mock_db_pr_request.pr_title, "Test PR Title from GH")
        self.assertEqual(self.mock_db_pr_request.pr_github_url, "http://github.com/pr/5")
        self.mock_db_session.commit.assert_called() # Kiểm tra commit được gọi sau khi cập nhật


    @patch("app.analysis_worker.consumer.crud_pr_analysis.get_pr_analysis_request_by_id")
    @patch("app.analysis_worker.consumer.crud_pr_analysis.update_pr_analysis_request_status")
    async def test_process_message_logic_pr_request_not_found(self, mock_update_status: MagicMock, mock_get_pr_req: MagicMock):
        mock_get_pr_req.return_value = None # Không tìm thấy PR request
        
        await consumer.process_message_logic(self.mock_kafka_message_value, self.mock_db_session)
        
        mock_get_pr_req.assert_called_once_with(self.mock_db_session, self.mock_kafka_message_value["pr_analysis_request_id"])
        mock_update_status.assert_not_called() # Không nên update status nếu request không tìm thấy

    @patch("app.analysis_worker.consumer.crud_pr_analysis.get_pr_analysis_request_by_id")
    @patch("app.analysis_worker.consumer.crud_pr_analysis.update_pr_analysis_request_status")
    async def test_process_message_logic_project_not_found(self, mock_update_status: MagicMock, mock_get_pr_req: MagicMock):
        mock_get_pr_req.return_value = self.mock_db_pr_request
        self.mock_db_session.query(Project).filter().first.return_value = None # Không tìm thấy project
        
        await consumer.process_message_logic(self.mock_kafka_message_value, self.mock_db_session)

        mock_update_status.assert_called_once_with(
            self.mock_db_session, self.mock_db_pr_request.id, 
            PRAnalysisStatus.FAILED, "Associated project not found"
        )

    @patch("app.analysis_worker.consumer.crud_pr_analysis.get_pr_analysis_request_by_id")
    @patch("app.analysis_worker.consumer.crud_pr_analysis.update_pr_analysis_request_status")
    @patch("app.analysis_worker.consumer.decrypt_data", return_value=None) # Giả lập decrypt lỗi
    async def test_process_message_logic_decrypt_token_fails(
        self, mock_decrypt: MagicMock, mock_update_status: MagicMock, mock_get_pr_req: MagicMock
    ):
        mock_get_pr_req.return_value = self.mock_db_pr_request
        self.mock_db_session.query(Project).filter().first.return_value = self.mock_db_project
        self.mock_db_session.query(User).filter().first.return_value = self.mock_db_user
        
        await consumer.process_message_logic(self.mock_kafka_message_value, self.mock_db_session)
        
        # update_status được gọi 2 lần: 1 cho PROCESSING, 1 cho FAILED
        self.assertEqual(mock_update_status.call_count, 2)
        mock_update_status.assert_any_call(self.mock_db_session, self.mock_db_pr_request.id, PRAnalysisStatus.PROCESSING)
        mock_update_status.assert_any_call(self.mock_db_session, self.mock_db_pr_request.id, PRAnalysisStatus.FAILED, "GitHub token decryption error")

    @patch("app.analysis_worker.consumer.crud_pr_analysis.get_pr_analysis_request_by_id")
    @patch("app.analysis_worker.consumer.crud_pr_analysis.update_pr_analysis_request_status")
    @patch("app.analysis_worker.consumer.decrypt_data")
    @patch("app.analysis_worker.consumer.GitHubAPIClient")
    async def test_process_message_logic_github_api_fails(
        self, MockGitHubAPIClient: MagicMock, mock_decrypt: MagicMock, 
        mock_update_status: MagicMock, mock_get_pr_req: MagicMock
    ):
        mock_get_pr_req.return_value = self.mock_db_pr_request
        self.mock_db_session.query(Project).filter().first.return_value = self.mock_db_project
        self.mock_db_session.query(User).filter().first.return_value = self.mock_db_user
        mock_decrypt.return_value = "decrypted_github_token_string"

        mock_gh_client_instance = MockGitHubAPIClient.return_value
        # Giả lập một phương thức API của GitHub lỗi
        mock_gh_client_instance.get_pull_request_details = AsyncMock(side_effect=Exception("GitHub API Call Failed"))
        
        await consumer.process_message_logic(self.mock_kafka_message_value, self.mock_db_session)
        
        self.assertEqual(mock_update_status.call_count, 2) # PROCESSING, FAILED
        mock_update_status.assert_any_call(self.mock_db_session, self.mock_db_pr_request.id, PRAnalysisStatus.PROCESSING)
        # Kiểm tra error_message có chứa thông báo lỗi không
        # Lấy lần gọi cuối cùng đến update_pr_analysis_request_status
        last_call_args = mock_update_status.call_args_list[-1][0] # Lấy positional args
        self.assertEqual(last_call_args[2], PRAnalysisStatus.FAILED) # status là FAILED
        self.assertIn("GitHub API Call Failed", last_call_args[3]) # error_message


# if __name__ == '__main__':
#     unittest.main()