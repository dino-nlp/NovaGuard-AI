import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx # Cần thiết để raise httpx exceptions trong mock

from app.common import GitHubAPIClient, GITHUB_API_BASE_URL, GITHUB_API_VERSION_HEADER

class TestGitHubAPIClient(unittest.IsolatedAsyncioTestCase): # Sử dụng IsolatedAsyncioTestCase cho các hàm async

    def setUp(self):
        self.test_token = "fake_github_token"
        self.owner = "testowner"
        self.repo = "testrepo"
        self.pr_number = 1
        self.file_path = "src/main.py"
        self.ref = "testsha123"
        self.client = GitHubAPIClient(token=self.test_token)

    async def test_init_no_token(self):
        with self.assertRaisesRegex(ValueError, "GitHub token is required for APIClient."):
            GitHubAPIClient(token="")

    @patch("app.common.github_client.httpx.AsyncClient")
    async def test_get_pull_request_details_success(self, MockAsyncClient):
        mock_response_data = {"title": "Test PR", "number": self.pr_number, "head": {"sha": self.ref}}
        
        # Cấu hình mock cho response của httpx
        mock_http_response = MagicMock(spec=httpx.Response)
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response_data
        
        # Cấu hình mock_client_instance.request hoặc mock_client_instance.get
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value # Lấy instance từ async context manager
        mock_client_instance.request.return_value = mock_http_response # Giả sử _request gọi client.request

        details = await self.client.get_pull_request_details(self.owner, self.repo, self.pr_number)

        expected_url = f"{GITHUB_API_BASE_URL}/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}"
        mock_client_instance.request.assert_called_once_with(
            "GET", expected_url, headers=self.client.headers
        )
        self.assertEqual(details, mock_response_data)

    @patch("app.common.github_client.httpx.AsyncClient")
    async def test_get_pull_request_details_failure(self, MockAsyncClient):
        mock_http_response = MagicMock(spec=httpx.Response)
        mock_http_response.status_code = 404
        mock_http_response.request = httpx.Request("GET", "http://example.com") # Cần cho HTTPStatusError
        mock_http_response.text = '{"message": "Not Found"}'
        mock_http_response.json.return_value = {"message": "Not Found"}
        
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        # raise_for_status() sẽ được gọi trong self.client._request
        mock_client_instance.request.side_effect = httpx.HTTPStatusError(
            message="Not Found", request=mock_http_response.request, response=mock_http_response
        )

        details = await self.client.get_pull_request_details(self.owner, self.repo, self.pr_number)
        self.assertIsNone(details)

    @patch("app.common.github_client.httpx.AsyncClient")
    async def test_get_pull_request_diff_success(self, MockAsyncClient):
        mock_diff_text = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new"
        mock_http_response = MagicMock(spec=httpx.Response)
        mock_http_response.status_code = 200
        mock_http_response.text = mock_diff_text
        
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        mock_client_instance.request.return_value = mock_http_response

        diff = await self.client.get_pull_request_diff(self.owner, self.repo, self.pr_number)
        
        expected_url = f"{GITHUB_API_BASE_URL}/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}"
        mock_client_instance.request.assert_called_once_with(
            "GET", expected_url, headers=self.client.diff_headers
        )
        self.assertEqual(diff, mock_diff_text)

    @patch("app.common.github_client.httpx.AsyncClient")
    async def test_get_pull_request_files_success_single_page(self, MockAsyncClient):
        mock_files_data = [{"filename": "file1.py", "status": "modified"}]
        mock_http_response = MagicMock(spec=httpx.Response)
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_files_data
        mock_http_response.headers = {} # Không có 'Link' header cho trang cuối

        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        mock_client_instance.request.return_value = mock_http_response

        files = await self.client.get_pull_request_files(self.owner, self.repo, self.pr_number)
        
        expected_url = f"{GITHUB_API_BASE_URL}/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}/files?per_page=100&page=1"
        mock_client_instance.request.assert_called_once_with(
            "GET", expected_url, headers=self.client.headers
        )
        self.assertEqual(files, mock_files_data)

    @patch("app.common.github_client.httpx.AsyncClient")
    async def test_get_pull_request_files_success_multiple_pages(self, MockAsyncClient):
        mock_files_page1 = [{"filename": f"file{i}.py"} for i in range(100)]
        mock_files_page2 = [{"filename": "file_final.py"}]

        # Mock response cho trang 1 (có link next)
        mock_response_page1 = MagicMock(spec=httpx.Response)
        mock_response_page1.status_code = 200
        mock_response_page1.json.return_value = mock_files_page1
        next_url = f"{GITHUB_API_BASE_URL}/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}/files?per_page=100&page=2"
        mock_response_page1.headers = {"Link": f'<{next_url}>; rel="next", <http://another_url>; rel="last"'}
        
        # Mock response cho trang 2 (không có link next)
        mock_response_page2 = MagicMock(spec=httpx.Response)
        mock_response_page2.status_code = 200
        mock_response_page2.json.return_value = mock_files_page2
        mock_response_page2.headers = {}

        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        mock_client_instance.request.side_effect = [mock_response_page1, mock_response_page2]

        files = await self.client.get_pull_request_files(self.owner, self.repo, self.pr_number)

        self.assertEqual(len(files), 101)
        self.assertEqual(files[-1]["filename"], "file_final.py")
        self.assertEqual(mock_client_instance.request.call_count, 2)
        
        first_call_args = mock_client_instance.request.call_args_list[0]
        self.assertEqual(first_call_args[0][1], f"{GITHUB_API_BASE_URL}/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}/files?per_page=100&page=1")
        
        second_call_args = mock_client_instance.request.call_args_list[1]
        self.assertEqual(second_call_args[0][1], next_url)


    @patch("app.common.github_client.httpx.AsyncClient")
    async def test_get_file_content_text_success(self, MockAsyncClient):
        mock_content_base64 = "cHJpbnQoJ2hlbGxvIHdvcmxkJyk=" # print('hello world') base64 encoded
        mock_response_data = {"content": mock_content_base64, "encoding": "base64"}
        
        mock_http_response = MagicMock(spec=httpx.Response)
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response_data
        
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        mock_client_instance.request.return_value = mock_http_response

        content = await self.client.get_file_content(self.owner, self.repo, self.file_path, self.ref)
        
        expected_url = f"{GITHUB_API_BASE_URL}/repos/{self.owner}/{self.repo}/contents/{self.file_path}"
        mock_client_instance.request.assert_called_once_with(
            "GET", expected_url, headers=self.client.headers, params={"ref": self.ref}
        )
        self.assertEqual(content, "print('hello world')")

    @patch("app.common.github_client.httpx.AsyncClient")
    async def test_get_file_content_binary(self, MockAsyncClient):
        # Giả lập file binary bằng cách cho decode lỗi
        mock_content_base64_binary = "////" # Not valid utf-8 after base64 decode
        mock_response_data = {"content": mock_content_base64_binary, "encoding": "base64"}
        
        mock_http_response = MagicMock(spec=httpx.Response)
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response_data
        
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        mock_client_instance.request.return_value = mock_http_response

        content = await self.client.get_file_content(self.owner, self.repo, "binary.data", self.ref)
        self.assertEqual(content, "[Binary Content - Not Decoded]")

# if __name__ == '__main__':
#     unittest.main()