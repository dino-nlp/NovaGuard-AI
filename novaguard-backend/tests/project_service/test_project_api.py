import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app # app FastAPI
from app.project_service import schemas as project_schemas
from app.auth_service import schemas as auth_schemas # Dùng cho UserPublic
# from app.models.project_model import Project # Không cần trực tiếp nếu mock crud tốt

client = TestClient(app)

# Dữ liệu người dùng giả lập cho dependency get_current_active_user
MOCK_USER_ID = 1
mock_current_user = auth_schemas.UserPublic(
    id=MOCK_USER_ID,
    email="testuser@example.com",
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc)
)

# --- Helper để mock get_current_active_user ---
async def override_get_current_active_user():
    return mock_current_user

# Ghi đè dependency trong app cho tất cả các test trong file này
from app.project_service.api import get_current_active_user as project_api_get_user # Lấy đúng dependency cần override
app.dependency_overrides[project_api_get_user] = override_get_current_active_user


class TestProjectAPI(unittest.TestCase):
    
    def common_project_data(self, project_id=1):
        now = datetime.now(timezone.utc)
        return {
            "id": project_id,
            "user_id": MOCK_USER_ID,
            "github_repo_id": f"gh_api_test_{project_id}",
            "repo_name": f"owner/api_test_project_{project_id}",
            "main_branch": "main",
            "language": "Python",
            "custom_project_notes": "API test notes",
            "created_at": now.isoformat().replace("+00:00", "Z"), # FastAPI sẽ trả về ISO string
            "updated_at": now.isoformat().replace("+00:00", "Z")
        }

    @patch("app.project_service.api.crud_project.create_project")
    def test_create_new_project_success(self, mock_create_project: MagicMock):
        project_payload = {
            "github_repo_id": "gh_api_create",
            "repo_name": "owner/api_create_test",
            "main_branch": "develop",
            "language": "Go"
        }
        # crud_project.create_project trả về SQLAlchemy model instance.
        # FastAPI sẽ convert nó sang ProjectPublic.
        # Chúng ta cần mock sao cho giá trị trả về có các trường cần thiết.
        mocked_db_project_instance = MagicMock()
        mocked_db_project_instance.id = 1
        mocked_db_project_instance.user_id = MOCK_USER_ID
        mocked_db_project_instance.github_repo_id = project_payload["github_repo_id"]
        mocked_db_project_instance.repo_name = project_payload["repo_name"]
        mocked_db_project_instance.main_branch = project_payload["main_branch"]
        mocked_db_project_instance.language = project_payload["language"]
        mocked_db_project_instance.custom_project_notes = None
        mocked_db_project_instance.created_at = datetime.now(timezone.utc)
        mocked_db_project_instance.updated_at = datetime.now(timezone.utc)

        mock_create_project.return_value = mocked_db_project_instance
        
        response = client.post("/projects/", json=project_payload) # Có token giả lập qua override_get_current_active_user

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["repo_name"], project_payload["repo_name"])
        self.assertEqual(data["user_id"], MOCK_USER_ID)
        self.assertIn("id", data)
        mock_create_project.assert_called_once()
        # Kiểm tra project_in và user_id được truyền vào crud_project.create_project
        args, kwargs = mock_create_project.call_args
        self.assertEqual(kwargs['project_in'].repo_name, project_payload["repo_name"])
        self.assertEqual(kwargs['user_id'], MOCK_USER_ID)

    @patch("app.project_service.api.crud_project.create_project")
    def test_create_project_conflict(self, mock_create_project: MagicMock):
        mock_create_project.return_value = None # Giả lập lỗi Integrity (project đã tồn tại)
        project_payload = {"github_repo_id": "gh_conflict", "repo_name": "owner/conflict", "main_branch": "main"}
        
        response = client.post("/projects/", json=project_payload)
        
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Project with this GitHub Repo ID already exists for this user.")

    @patch("app.project_service.api.crud_project.get_projects_by_user")
    def test_read_user_projects(self, mock_get_projects: MagicMock):
        # Giả lập crud_project.get_projects_by_user trả về list các project model instances
        mocked_db_project_1 = MagicMock()
        mocked_db_project_1.id=1; mocked_db_project_1.user_id=MOCK_USER_ID; mocked_db_project_1.repo_name="p1"
        mocked_db_project_1.github_repo_id="g1"; mocked_db_project_1.main_branch="m"; mocked_db_project_1.language="L1"
        mocked_db_project_1.custom_project_notes="N1"; mocked_db_project_1.created_at=datetime.now(timezone.utc); mocked_db_project_1.updated_at=datetime.now(timezone.utc)

        mock_get_projects.return_value = [mocked_db_project_1]
        
        response = client.get("/projects/?skip=0&limit=10")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["projects"]), 1)
        self.assertEqual(data["projects"][0]["repo_name"], "p1")
        self.assertEqual(data["total"], 1) # Dựa trên logic hiện tại của API
        mock_get_projects.assert_called_once_with(db=unittest.mock.ANY, user_id=MOCK_USER_ID, skip=0, limit=10)

    @patch("app.project_service.api.crud_project.get_project_by_id")
    def test_read_project_details_found(self, mock_get_project: MagicMock):
        # Giả lập crud_project.get_project_by_id trả về project model instance
        project_id_to_test = 7
        mocked_db_project = MagicMock()
        mocked_db_project.id=project_id_to_test; mocked_db_project.user_id=MOCK_USER_ID; mocked_db_project.repo_name="detail_test"
        mocked_db_project.github_repo_id="g_detail"; mocked_db_project.main_branch="m_detail"; mocked_db_project.language="L_detail"
        mocked_db_project.custom_project_notes="N_detail"; mocked_db_project.created_at=datetime.now(timezone.utc); mocked_db_project.updated_at=datetime.now(timezone.utc)

        mock_get_project.return_value = mocked_db_project
        
        response = client.get(f"/projects/{project_id_to_test}")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["repo_name"], "detail_test")
        self.assertEqual(data["id"], project_id_to_test)
        mock_get_project.assert_called_once_with(db=unittest.mock.ANY, project_id=project_id_to_test, user_id=MOCK_USER_ID)

    @patch("app.project_service.api.crud_project.get_project_by_id")
    def test_read_project_details_not_found(self, mock_get_project: MagicMock):
        mock_get_project.return_value = None
        response = client.get("/projects/999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Project not found or not owned by user")

    @patch("app.project_service.api.crud_project.update_project")
    def test_update_project_success(self, mock_update_project: MagicMock):
        project_id_to_update = 5
        update_payload = {"repo_name": "updated_name", "language": "Rust"}

        # Giả lập crud_project.update_project trả về project model instance đã được update
        mocked_updated_db_project = MagicMock()
        mocked_updated_db_project.id=project_id_to_update; mocked_updated_db_project.user_id=MOCK_USER_ID; 
        mocked_updated_db_project.repo_name=update_payload["repo_name"]; mocked_updated_db_project.language=update_payload["language"]
        mocked_updated_db_project.github_repo_id="g_update"; mocked_updated_db_project.main_branch="m_update"; 
        mocked_updated_db_project.custom_project_notes="N_update"; mocked_updated_db_project.created_at=datetime.now(timezone.utc); mocked_updated_db_project.updated_at=datetime.now(timezone.utc)
        
        mock_update_project.return_value = mocked_updated_db_project
        
        response = client.put(f"/projects/{project_id_to_update}", json=update_payload)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["repo_name"], "updated_name")
        self.assertEqual(data["language"], "Rust")
        mock_update_project.assert_called_once()
        args, kwargs = mock_update_project.call_args
        self.assertEqual(kwargs['project_id'], project_id_to_update)
        self.assertEqual(kwargs['project_in'].repo_name, update_payload["repo_name"])
        self.assertEqual(kwargs['user_id'], MOCK_USER_ID)

    @patch("app.project_service.api.crud_project.update_project")
    def test_update_project_not_found(self, mock_update_project: MagicMock):
        mock_update_project.return_value = None
        response = client.put("/projects/999", json={"repo_name": "test"})
        self.assertEqual(response.status_code, 404)

    @patch("app.project_service.api.crud_project.delete_project")
    def test_delete_project_success(self, mock_delete_project: MagicMock):
        project_id_to_delete = 3
        # Giả lập crud_project.delete_project trả về project model instance đã bị xóa
        mocked_deleted_db_project = MagicMock()
        mocked_deleted_db_project.id=project_id_to_delete; mocked_deleted_db_project.user_id=MOCK_USER_ID; 
        mocked_deleted_db_project.repo_name="deleted_project_name"; 
        # ... các trường khác nếu response_model cần ...
        mocked_deleted_db_project.github_repo_id="g_del"; mocked_deleted_db_project.main_branch="m_del"; mocked_deleted_db_project.language="L_del"
        mocked_deleted_db_project.custom_project_notes="N_del"; mocked_deleted_db_project.created_at=datetime.now(timezone.utc); mocked_deleted_db_project.updated_at=datetime.now(timezone.utc)

        mock_delete_project.return_value = mocked_deleted_db_project
        
        response = client.delete(f"/projects/{project_id_to_delete}")
        
        self.assertEqual(response.status_code, 200) # Hoặc 204 nếu API không trả về body
        data = response.json()
        self.assertEqual(data["repo_name"], "deleted_project_name") # Kiểm tra response body
        mock_delete_project.assert_called_once_with(db=unittest.mock.ANY, project_id=project_id_to_delete, user_id=MOCK_USER_ID)

    @patch("app.project_service.api.crud_project.delete_project")
    def test_delete_project_not_found(self, mock_delete_project: MagicMock):
        mock_delete_project.return_value = None
        response = client.delete("/projects/999")
        self.assertEqual(response.status_code, 404)

# Clean up dependency override after tests if necessary (though for TestClient it's usually fine per file)
# Hoặc dùng fixture của pytest để quản lý dependency_overrides tốt hơn
# def tearDownModule():
#     app.dependency_overrides = {}

if __name__ == '__main__':
    unittest.main()