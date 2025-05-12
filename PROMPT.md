Chúng ta sẽ cùng nhau phát triển phần mềm NovaGuard-AI 2.0 – Nền tảng Phân tích Code Thông minh và Chuyên sâu

Dưới đây là yêu cầu cũng như design của dự án:

**Mục tiêu cho Giai đoạn này (MVP1):**
Xây dựng nền tảng web cơ bản cho NovaGuard-AI 2.0, cho phép người dùng thêm các dự án GitHub và nhận được các đánh giá code thông minh, được hỗ trợ bởi LLM, cho các Pull Request của họ. Trọng tâm chính là tính năng "Đánh giá PR Tự động", quản lý người dùng và dự án cơ bản, và thiết lập ban đầu cho bộ máy phân tích.

**Tài liệu Thiết kế Tham chiếu:**
Prompt này dựa trên "Bản Thiết kế Dự án: NovaGuard-AI 2.0" chi tiết đã được thống nhất. Vui lòng xem xét các nguyên tắc kiến trúc, các khái niệm cốt lõi (MCP, CKG - mặc dù CKG sẽ được đơn giản hóa cho MVP1), và tầm nhìn tổng thể được nêu trong tài liệu đó.

**LƯU Ý CỰC KỲ QUAN TRỌNG VỀ GIẤY PHÉP (LICENSE):**
* **Ưu tiên Open Source và Thương mại hóa:** Toàn bộ dự án này hướng tới việc sử dụng cho doanh nghiệp. Do đó, tất cả các thư viện và công cụ bên ngoài được sử dụng **PHẢI** là mã nguồn mở và có giấy phép cho phép sử dụng thương mại.
* **Linh hoạt về Giấy phép Dự án:** NovaGuard-AI (sản phẩm cuối) **KHÔNG** được bị ràng buộc bởi giấy phép của bất kỳ thư viện nào được sử dụng (ví dụ: không muốn dự án phải theo GPL chỉ vì dùng một thư viện GPL). Chúng ta sẽ ưu tiên các thư viện có giấy phép "permissive" như MIT, Apache 2.0, BSD.
* **Trách nhiệm Kiểm tra License Model LLM:** Giấy phép của từng model LLM cụ thể (ví dụ: Llama, Mistral, Qwen) mà bạn chọn để tích hợp với Ollama **PHẢI** được kiểm tra riêng biệt bởi người quản lý dự án để đảm bảo tuân thủ các điều khoản sử dụng thương mại của chúng.
* Vui lòng thông báo nếu có bất kỳ đề xuất công nghệ nào có thể không đáp ứng các yêu cầu nghiêm ngặt này.

**I. Tổng Quan Kiến Trúc Cấp Cao (Tập trung cho MVP1):**

1.  **Frontend (Ứng dụng Web Đơn Trang - SPA):** Giao diện người dùng cho đăng ký, đăng nhập, quản lý dự án, và xem báo cáo đánh giá PR.
2.  **Backend API Gateway:** Điểm vào cho các yêu cầu từ frontend.
3.  **Core Analysis Engine (Bộ máy Phân tích Lõi - Backend):**
    * Project Manager Service (Tích hợp GitHub)
    * Webhook Handler Service (Xử lý sự kiện PR từ GitHub)
    * Analysis Orchestrator Service (Đơn giản hóa cho việc đánh giá PR, MCP cơ bản)
    * LLM Service Wrapper (Tích hợp Ollama)
    * Report Generator Service (Cấu trúc báo cáo cơ bản)
4.  **Data Persistence Layer (Lớp Lưu trữ Dữ liệu):** Lưu trữ dữ liệu người dùng, dự án, và kết quả đánh giá.
5.  **Job Queue & Worker System (Hàng đợi Tác vụ & Hệ thống Worker):** Cho việc phân tích PR bất đồng bộ.
6.  **Authentication & Authorization Service (Dịch vụ Xác thực & Phân quyền):** Đăng nhập người dùng và kiểm soát truy cập.

**II. Công Nghệ Đề Xuất (Cho phát triển ban đầu - Đã rà soát license):**

* **Frontend:** React với TypeScript (Giấy phép MIT, Apache 2.0), Tailwind CSS (Giấy phép MIT).
* **Backend API Gateway & Microservices:** Python 3.10+ với FastAPI (Giấy phép Python, MIT).
* **LLM Orchestration:** Langchain/LangGraph (Python - Giấy phép MIT).
* **LLM Runtime:** Ollama (Giấy phép MIT). *Lưu ý kiểm tra license của từng model LLM riêng bởi người quản lý dự án.*
* **Cơ sở dữ liệu Quan hệ:** PostgreSQL (Giấy phép PostgreSQL - permissive).
* **Hàng đợi Tin nhắn (Message Queue):**
    * **Lựa chọn 1 (Ưu tiên nếu muốn tránh mọi copyleft):** Apache Kafka (Giấy phép Apache 2.0 - permissive).
    * **Lựa chọn 2 (Thường được chấp nhận cho thương mại):** RabbitMQ (Giấy phép MPL 2.0 - copyleft yếu, file-level; việc sử dụng như một service riêng biệt thường không yêu cầu dự án phải theo MPL 2.0).
* **Containerization (Đóng gói):** Docker (Engine - Giấy phép Apache 2.0).
* **Graph Database (cho CKG - MVP sau này, nhưng cần định hướng sớm):**
    * **Lựa chọn Ưu tiên để tránh GPL:** **ArangoDB** (Phiên bản Community - Giấy phép Apache 2.0).
    * **Lựa chọn khác:** **Apache AGE** (Extension cho PostgreSQL - Giấy phép Apache 2.0).
    * *Lưu ý: Tránh Neo4j Community Edition (GPLv3) nếu muốn duy trì sự linh hoạt về license cho NovaGuard-AI.*
* **Vector Database (cho Semantic Embeddings - MVP sau này):** ChromaDB (Giấy phép Apache 2.0) hoặc Weaviate (Giấy phép BSD 3-Clause).
* **AST Parsing (MVP sau này, khi CKG phức tạp hơn):** `tree-sitter` (Giấy phép MIT).

**III. Các Khái Niệm Cốt Lõi cần Triển khai (Đơn giản hóa cho MVP1):**

1.  **Model Context Protocol (MCP) - Triển khai Cơ bản:**
    * `Analysis Orchestrator Service` sẽ thu thập một `DynamicProjectContext` cơ bản cho mỗi PR. Đối với MVP1, context này chủ yếu bao gồm:
        * Metadata của PR (tác giả, tiêu đề, tên nhánh).
        * Nội dung code diff.
        * Nội dung của các file đã thay đổi.
        * Ngôn ngữ dự án (lấy từ cài đặt dự án).
        * Các quy ước code cơ bản của dự án (nếu có thể cấu hình trong UI của MVP1).
2.  **Code Knowledge Graph (CKG) - Tối thiểu cho MVP1:**
    * Đối với MVP1, chúng ta sẽ **không** triển khai một Graph Database đầy đủ cho CKG.
    * Thay vào đó, `Analysis Orchestrator Service` (cụ thể là một node `ContextEnrichmentNode` đơn giản hóa) có thể thực hiện phân tích nhẹ, "on-the-fly" các file đã thay đổi và có thể là các import trực tiếp của chúng để xây dựng một ngữ cảnh cục bộ tạm thời cho PR.
    * Mục tiêu là cung cấp cho các agent LLM một chút ngữ cảnh nhiều hơn là chỉ có diff.

**IV. Các Tính Năng Chính cho Phát triển MVP1:**

1.  **Quản lý Người dùng & Xác thực:**
    * Đăng ký người dùng (email/password).
    * Đăng nhập người dùng.
    * GitHub OAuth để kết nối tài khoản GitHub (lấy thông tin user và quyền truy cập repo).
2.  **Quản lý Dự án:**
    * **"Thêm Dự án Mới":**
        * Người dùng kết nối tài khoản GitHub của họ.
        * Người dùng chọn một repository từ danh sách repo họ có quyền truy cập.
        * Người dùng chọn nhánh chính (ví dụ: `main`, `master`) để theo dõi.
        * Lưu trữ metadata cơ bản của dự án (ID repo, tên, nhánh chính) và thông tin tích hợp GitHub (ví dụ: token truy cập liên quan đến user đó cho repo đó).
    * **Dashboard Dự án (MVP1):** Một danh sách đơn giản các dự án người dùng đã thêm. Nhấp vào một dự án sẽ hiển thị danh sách các PR của nó đã/đang được phân tích (hoặc link tới trang chi tiết PR).
3.  **Đánh giá PR Tự động (Tính năng Cốt lõi):**
    * **Kích hoạt:** Qua GitHub webhook khi một PR được tạo hoặc cập nhật (commit mới) cho một dự án đã được thêm vào NovaGuard-AI.
    * **Quy trình:**
        1.  `Webhook Handler Service` nhận sự kiện, xác thực, và đưa một tác vụ phân tích vào `Job Queue`.
        2.  Một `Worker Process` (`analysis_worker`) lấy tác vụ.
        3.  `Project Manager Service` lấy chi tiết PR (metadata, diff URL) và nội dung code diff.
        4.  `Analysis Orchestrator Service` (phiên bản MVP1):
            * `InitializeContextNode`: Tạo `DynamicProjectContext` cơ bản với thông tin PR và diff.
            * `ContextEnrichmentNode` (MVP1): Làm giàu context bằng cách đọc và thêm nội dung đầy đủ của các file đã thay đổi vào `DynamicProjectContext`. (Phân tích AST cơ bản cho các import trực tiếp có thể xem xét nếu không quá phức tạp cho MVP1).
            * Kích hoạt **MỘT Agent Chuyên sâu chính** (ví dụ: `DeepLogicBugHunterAI_MVP1` với một bộ quy tắc/prompt ban đầu tập trung vào các lỗi logic phổ biến và dễ phát hiện khi có ngữ cảnh file).
            * `LLM Service Wrapper` tương tác với Ollama sử dụng các prompt được làm giàu bởi `DynamicProjectContext`.
            * `ReportGeneratorService`: Tạo một cấu trúc báo cáo (ví dụ: JSON) về các phát hiện.
        5.  Lưu trữ kết quả phân tích (các phát hiện) vào cơ sở dữ liệu, liên kết với PR và dự án.
4.  **Hiển thị Báo cáo Đánh giá PR:**
    * Trên frontend, một trang riêng cho mỗi PR được phân tích, hiển thị:
        * Thông tin cơ bản của PR (tiêu đề, tác giả, link GitHub).
        * Danh sách các phát hiện/gợi ý từ NovaGuard-AI.
        * Mỗi phát hiện bao gồm: đường dẫn file, (các) số dòng liên quan, mức độ nghiêm trọng (ví dụ: "Lỗi", "Cảnh báo", "Ghi chú"), một thông điệp mô tả vấn đề, và bất kỳ gợi ý sửa lỗi nào do LLM tạo ra.
        * (Tùy chọn MVP1) Khả năng người dùng đưa phản hồi cơ bản cho từng phát hiện (ví dụ: "Hữu ích", "Không hữu ích").
5.  **Giao diện Cấu hình Dự án Cơ bản (MVP1):**
    * Cho phép người dùng chỉ định ngôn ngữ lập trình chính của dự án (để hỗ trợ prompt tốt hơn).
    * (Tùy chọn MVP1) Một vùng văn bản đơn giản để người dùng nhập một vài quy ước code hoặc ghi chú kiến trúc quan trọng của dự án, những thông tin này sẽ được đưa vào `DynamicProjectContext`.

**V. Phân Rã Module/Service cho Coding Ban đầu (Tập trung MVP1):**

Vui lòng cấu trúc codebase thành các module/service chính sau. Đối với mỗi module, phác thảo trách nhiệm chính và các chức năng chủ chốt.

1.  **Ứng dụng Frontend (ví dụ: `novaguard-ui`):**
    * **Các Trang/Component:**
        * Trang Đăng nhập / Đăng ký (có lựa chọn "Đăng nhập bằng GitHub").
        * Trang Dashboard: Hiển thị danh sách các dự án đã thêm.
        * Trang Chi tiết Dự án: Hiển thị danh sách các PR đã được review cho dự án đó.
        * Trang Báo cáo Đánh giá PR: Hiển thị chi tiết các phát hiện của một PR.
        * Trang Thêm Dự án Mới (sau khi xác thực GitHub, cho phép chọn repo).
        * Trang Cài đặt Dự án Cơ bản (chỉnh sửa ngôn ngữ, ghi chú).
    * **Chức năng:** Gọi API đến backend, quản lý state (ví dụ: Redux, Zustand), render UI.

2.  **Các Dịch vụ Backend (ví dụ: trong một monorepo `novaguard-backend` hoặc các service riêng biệt):**

    * **`auth_service` (Dịch vụ Xác thực):**
        * **Mục đích:** Xử lý đăng ký người dùng (email/password), đăng nhập, quản lý session/token, và luồng GitHub OAuth để lấy token truy cập GitHub của người dùng.
        * **API Endpoints (Ví dụ):**
            * `POST /auth/register`
            * `POST /auth/login`
            * `POST /auth/logout`
            * `GET /auth/github` (chuyển hướng đến GitHub)
            * `GET /auth/github/callback` (xử lý callback từ GitHub, lưu token)
        * **Mô hình DB:** `User` (id, email, hashed_password, github_user_id, github_access_token (mã hóa), created_at, updated_at).
    * **`project_service` (Dịch vụ Dự án):**
        * **Mục đích:** Quản lý thông tin dự án, tương tác với GitHub API (sử dụng token của người dùng) để lấy danh sách repo, chi tiết repo, và thiết lập webhook.
        * **API Endpoints (Ví dụ):**
            * `POST /projects` (Thêm dự án mới, payload: github_repo_id, main_branch_name, name)
            * `GET /projects` (Lấy danh sách dự án của user hiện tại)
            * `GET /projects/{project_id}` (Lấy chi tiết một dự án)
            * `PUT /projects/{project_id}` (Cập nhật cài đặt dự án: language, custom_notes)
            * `GET /projects/{project_id}/prs` (Lấy danh sách PR đã được review)
        * **Chức năng:** Thiết lập webhook trên GitHub cho repo khi thêm dự án.
        * **Mô hình DB:** `Project` (id, user_id (FK to User), github_repo_id, name, main_branch_name, language, custom_notes, webhook_id, created_at, updated_at).
    * **`webhook_service` (Dịch vụ Webhook):**
        * **Mục đích:** Tiếp nhận và xác thực các sự kiện webhook từ GitHub (chủ yếu là `pull_request` events: opened, synchronize).
        * **API Endpoints (Ví dụ):** `POST /webhooks/github`.
        * **Chức năng:** Phân tích payload webhook, xác định thông tin cần thiết (repo_id, pr_number, commit_sha, diff_url), tạo một tác vụ phân tích (`PRAnalysisTask`) và gửi nó đến `Job Queue`.
    * **`analysis_worker` (Tiến trình worker, không phải service API trực tiếp):**
        * **Mục đích:** Lấy các tác vụ `PRAnalysisTask` từ `Job Queue` và thực hiện quy trình phân tích PR.
        * **Chức năng:**
            1.  Lấy thông tin chi tiết PR và code diff từ GitHub (qua `Project Manager Service` hoặc trực tiếp bằng GitHub API client).
            2.  Gọi `Analysis Orchestrator Service` để thực hiện phân tích.
            3.  Lưu kết quả phân tích (`AnalysisFinding`) vào cơ sở dữ liệu.
            4.  Cập nhật trạng thái của `PRAnalysisRequest` (ví dụ: "pending", "processing", "completed", "failed").
    * **`analysis_orchestrator_service` (Logic nội bộ, được `analysis_worker` sử dụng):**
        * **Mục đích:** Điều phối các bước trong một phiên phân tích PR.
        * **Các Thành phần (Python classes/functions):**
            * `create_initial_context(pr_data, diff_data) -> DynamicProjectContext`: Tạo `DynamicProjectContext` ban đầu.
            * `enrich_context(current_context, changed_files_content) -> DynamicProjectContext`: Làm giàu context.
            * `DeepLogicBugHunterAgent_MVP1.run(context) -> List[Finding]`: Logic của agent.
            * `generate_report_structure(findings) -> StructuredReport`: Tạo cấu trúc báo cáo.
        * **Mô hình Dữ liệu (để lưu vào DB):**
            * `PRAnalysisRequest` (id, project_id (FK), pr_number, pr_title, pr_github_url, head_sha, status VARCHAR(20) CHECK (status IN ('pending', 'processing', 'completed', 'failed')), error_message TEXT, requested_at, started_at, completed_at).
            * `AnalysisFinding` (id, pr_analysis_request_id (FK), file_path VARCHAR(1024), line_start INT, line_end INT, severity VARCHAR(50) CHECK (severity IN ('Error', 'Warning', 'Note', 'Info')), message TEXT, suggestion TEXT, agent_name VARCHAR(100), user_feedback VARCHAR(50), created_at).
    * **`llm_service_wrapper` (Module Python nội bộ):**
        * **Mục đích:** Trừu tượng hóa việc giao tiếp với Ollama.
        * **Chức năng chính:** Phương thức `invoke_ollama(prompt: str, model_name: str) -> str`. Xử lý việc gửi request đến Ollama server, nhận response, xử lý lỗi cơ bản.
    * **`report_service` (Có thể là một phần của `project_service` hoặc API riêng):**
        * **Mục đích:** Cung cấp API endpoints cho frontend để lấy thông tin báo cáo phân tích đã hoàn thành.
        * **API Endpoints (Ví dụ):** `GET /projects/{project_id}/prs/{pr_number}/report` hoặc `GET /analysis_reports/{pr_analysis_request_id}`.

3.  **Lưu trữ Dữ liệu (PostgreSQL):**
    * **Schema SQL ban đầu:**
        * `Users` (id SERIAL PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL, password_hash TEXT NOT NULL, github_user_id VARCHAR(255) UNIQUE, github_access_token_encrypted TEXT, created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP)
        * `Projects` (id SERIAL PRIMARY KEY, user_id INT REFERENCES Users(id) ON DELETE CASCADE, github_repo_id VARCHAR(255) NOT NULL, repo_name VARCHAR(255) NOT NULL, main_branch VARCHAR(255) NOT NULL, language VARCHAR(100), custom_project_notes TEXT, github_webhook_id VARCHAR(255), created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, github_repo_id))
        * `PRAnalysisRequests` (id SERIAL PRIMARY KEY, project_id INT REFERENCES Projects(id) ON DELETE CASCADE, pr_number INT NOT NULL, pr_title TEXT, pr_github_url VARCHAR(2048), head_sha VARCHAR(40), status VARCHAR(20) CHECK (status IN ('pending', 'processing', 'completed', 'failed')) DEFAULT 'pending', error_message TEXT, requested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP, started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ)
        * `AnalysisFindings` (id SERIAL PRIMARY KEY, pr_analysis_request_id INT REFERENCES PRAnalysisRequests(id) ON DELETE CASCADE, file_path VARCHAR(1024) NOT NULL, line_start INT, line_end INT, severity VARCHAR(50) CHECK (severity IN ('Error', 'Warning', 'Note', 'Info')) NOT NULL, message TEXT NOT NULL, suggestion TEXT, agent_name VARCHAR(100), user_feedback VARCHAR(50), created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP)

4.  **Hàng đợi Tác vụ (Ví dụ: `pr_analysis_tasks` trên Apache Kafka hoặc RabbitMQ):**
    * Message payload sẽ chứa thông tin cần thiết để worker bắt đầu, ví dụ: `{ "project_id": ..., "pr_analysis_request_id": ..., "diff_url": ..., "head_sha": ..., "github_access_token": ... }`. (Lưu ý về việc truyền token một cách an toàn).

**VI. Nguyên Tắc Phát Triển:**

* **Tính Module (Modularity):** Thiết kế các service và component càng độc lập càng tốt, giao tiếp qua API rõ ràng.
* **Khả năng Kiểm thử (Testability):** Viết unit test cho logic nghiệp vụ quan trọng và integration test cho các luồng chính.
* **Khả năng Mở rộng (Scalability):** Kiến trúc backend nên hỗ trợ việc scale các worker và API service một cách độc lập.
* **Phong cách Code (Code Style):**
    * Python: Sử dụng type hints, tuân theo PEP 8, sử dụng Pydantic cho data validation.
    * Frontend: Tuân theo các thực hành chuẩn cho React/TypeScript.
* **Ghi Log (Logging):** Triển khai ghi log có cấu trúc (ví dụ: JSON) trong các dịch vụ backend để dễ dàng cho việc gỡ lỗi và giám sát.
* **Xử lý Lỗi (Error Handling):** Xử lý lỗi một cách nhất quán, trả về mã lỗi và thông điệp lỗi phù hợp cho API.
* **Bảo mật (Security):**
    * Xác thực và ủy quyền cho tất cả các API endpoint.
    * Mã hóa các thông tin nhạy cảm (ví dụ: GitHub access tokens).
    * Bảo vệ chống lại các lỗ hổng web phổ biến (OWASP Top 10).
    * Xác thực payload webhook từ GitHub (sử dụng secret).

**VII. Output Mong Muốn cho Giai đoạn này (MVP1):**

1.  **Source Code:** Toàn bộ mã nguồn cho frontend và các backend service/module.
2.  **Cấu trúc Thư mục:** Đề xuất cấu trúc thư mục rõ ràng cho từng phần của dự án.
3.  **Database Schema:** File SQL định nghĩa schema cho PostgreSQL.
4.  **Định nghĩa API:** Đặc tả OpenAPI (Swagger) cho các backend API.
5.  **Hướng dẫn Cài đặt và Chạy:**
    * `Dockerfile` cho mỗi service.
    * `docker-compose.yml` để thiết lập và chạy toàn bộ môi trường phát triển local (bao gồm database, message queue, Ollama, và các service của NovaGuard-AI).
    * Hướng dẫn chi tiết các bước để build và chạy dự án, bao gồm cả việc thiết lập GitHub App/OAuth App và webhook.
6.  **Một danh sách các giả định đã đặt ra trong quá trình code hoặc các câu hỏi làm rõ (nếu có).**

**VIII. Các Bước Tiếp Theo (Ngoài MVP1 - Để tham khảo):**

MVP1 này là nền tảng vững chắc. Các giai đoạn phát triển trong tương lai sẽ tập trung vào:
* Triển khai tính năng "Scan Toàn bộ Dự án."
* Xây dựng và tích hợp Code Knowledge Graph (CKG) với Graph Database (ví dụ: ArangoDB).
* Nâng cao `DynamicProjectContext` và các cơ chế của MCP.
* Thêm các Agent chuyên sâu hơn (`ArchitecturalAnalystAI`, `SecuritySentinelAI`, `PerformanceProfilerAI`).
* Cải thiện hệ thống báo cáo, thêm trực quan hóa dữ liệu và CKG.
* Hoàn thiện cơ chế phản hồi người dùng và khả năng "học" của hệ thống.
* Hỗ trợ các nền tảng quản lý source code khác.

###

Lưu ý cuối cùng để gửi tới Coding Partner:
- Khi tạo cấu trúc folder cho project cần kèm code file bash để dễ dàng tạo nhanh.
- Với mỗi class hay function được tạo ra, cần phải có unit test để đảm bảo tính đúng đắn của code
- Viết code có cấu trúc tốt để dễ dàng mở rộng, thay đổi
- Bám sát vào design, tránh đi lạc hướng.
- Tất cả các thư viện phải đảm bảo là opensource, không có ràng buộc về license của project, phù hợp dự án hướng tới doanh nghiệp.

Chúng ta sẽ cùng tạo ra một phần mềm hữu ích cho cộng đồng.