
## Báo cáo Dự án: NovaGuard AI – Người Đồng Hành Review Code Thông Minh Của Bạn

**Ngày:** 7 tháng 5 năm 2025

**Tầm nhìn:** Trao quyền cho các nhóm phát triển bằng một hệ thống review code tự động, thông minh, bảo mật và tùy biến cao, giúp nâng cao chất lượng mã nguồn, tăng tốc độ phát triển và giảm thiểu rủi ro.

**Mục tiêu Dự án:**
Xây dựng một GitHub Action tiên tiến, sử dụng hệ thống Đa Agent Lai (Hybrid Multi-Agent System) kết hợp sức mạnh của các công cụ phân tích tĩnh truyền thống và các mô hình ngôn ngữ lớn (LLM) thế hệ mới nhất (thông qua Ollama, chạy trên máy local). Hệ thống này sẽ tự động review merge request, đưa ra những nhận xét, cảnh báo và gợi ý cải thiện code một cách toàn diện và dễ hiểu.

**Vấn đề Cốt lõi Giải quyết:**
* **Thời gian review thủ công kéo dài:** Giảm tải cho các senior developer, để họ tập trung vào các vấn đề kiến trúc phức tạp hơn.
* **Bỏ sót lỗi tiềm ẩn:** Con người dễ bỏ sót lỗi, đặc biệt là các side effect tinh vi hoặc lỗ hổng bảo mật ít gặp.
* **Thiếu nhất quán trong review:** Đảm bảo các tiêu chuẩn code và chất lượng được áp dụng đồng đều.
* **Rào cản kiến thức:** Không phải ai cũng là chuyên gia về mọi mặt (bảo mật, tối ưu hóa, các pattern mới).
* **Lo ngại về bảo mật code:** Giữ code của dự án hoàn toàn trong môi trường local, không gửi đi bất kỳ đâu.

**Giải pháp Đề xuất: Hệ thống NovaGuard AI**

NovaGuard AI là một hệ thống Đa Agent Lai được thiết kế để hoạt động như một "người đồng hành" review code thông minh.

**I. Kiến trúc Tổng thể:**

* **Agent Điều phối Trung tâm (Orchestrator Agent):** "Bộ não" của NovaGuard AI.
    * **Tiếp nhận & Phân tích Thông minh:** Nhận dữ liệu merge request, thực hiện phân tích `diff` và ngữ cảnh liên quan.
    * **Kích hoạt Agent theo Tầng:**
        * **Tầng 1 (Fast Pass):** Kích hoạt các công cụ linter, formatter, SAST cơ bản và agent LLM nhẹ để có phản hồi nhanh về lỗi cú pháp, phong cách, và các vấn đề nghiêm trọng dễ thấy.
        * **Tầng 2 (Deep Analysis):** Kích hoạt các agent LLM mạnh mẽ hơn để phân tích sâu lỗi logic, side effect, bảo mật phức tạp, tối ưu hóa. Có thể chạy song song hoặc theo yêu cầu.
    * **Quản lý Ngữ cảnh Chung (Shared Context):** Chia sẻ thông tin (kết quả từ tool, loại ngôn ngữ, v.v.) giữa các agent.
    * **Tổng hợp & Tinh chỉnh Thông minh:** Thu thập kết quả, áp dụng điểm tin cậy (confidence scoring) cho gợi ý LLM, lọc nhiễu.
    * **(Nâng cao) Agent Siêu Giám định (Meta-Review LLM Agent):** Một LLM cuối cùng kiểm tra, tổng hợp và cải thiện chất lượng toàn bộ các gợi ý.
    * **Báo cáo Thân thiện:** Tạo comment trên GitHub dễ đọc, có tóm tắt, giải thích "tại sao" và gợi ý "cách sửa".
    * **Vòng lặp Phản hồi:** Cho phép người dùng đánh giá gợi ý để cải thiện hệ thống.
    * **Cấu hình Linh hoạt:** Mọi thứ (prompts, models, tool paths, rules) được quản lý qua file cấu hình.

**II. Thiết kế Chi tiết các Agent Chuyên biệt (Phương pháp Lai):**

1.  **Guardian Style (Agent Phân tích Cấu trúc & Phong cách Code):**
    * **Công cụ:** Chạy linter (ESLint, Pylint, Checkstyle, SwiftLint, etc.) & formatter.
    * **LLM (ví dụ: `qwen3-coder:15b-instruct`, `codellama-v3:13b-style` - bản T5/2025):** Giải thích output của tool, gợi ý sửa lỗi phức tạp, phát hiện vấn đề phong cách sâu hơn, kiểm tra comment.

2.  **BugHunter AI (Agent Phát hiện Lỗi Tiềm ẩn & Phân tích Luồng):**
    * **Công cụ (Tùy chọn):** Các tool tìm bug tĩnh nhẹ.
    * **LLM (ví dụ: `deepseek-coder-v2:33b-instruct`, `wizardcoder-evo:30b` - bản T5/2025):** Săn lỗi logic, null pointer, rò rỉ tài nguyên, phân tích side effect, gợi ý test case.

3.  **SecuriSense AI (Agent Kiểm tra Bảo mật Chuyên sâu):**
    * **Công cụ (Bắt buộc):** Các công cụ SAST mạnh mẽ (Semgrep, SonarScanner local, OWASP ZAP passive, etc.).
    * **LLM (ví dụ: `securecode-llama:20b-instruct`, `qwen3-sec:15b-chat` - bản T5/2025):** Sàng lọc false positive từ SAST, ưu tiên lỗ hổng, giải thích nguy cơ, đề xuất vá lỗi, và cố gắng tìm các mẫu không an toàn mới (cần cẩn trọng).

4.  **OptiTune AI (Agent Đề xuất Tối ưu hóa & Hiện đại hóa Code):**
    * **LLM (ví dụ: `codegemma-plus:12b-instruct`, `qwen3-coder:15b-instruct` - bản T5/2025):** Tìm điểm nghẽn hiệu năng, gợi ý dùng tính năng ngôn ngữ mới, thuật toán hiệu quả, refactor để dễ bảo trì.

**III. Công nghệ Nền tảng:**

* **GitHub Actions:** Nền tảng tự động hóa workflow.
* **Self-hosted Runner:** Đảm bảo chạy trên máy local của bạn.
* **Ollama:** Để chạy các LLM offline.
* **Mô hình LLM (Tháng 5/2025):** Các model open source mạnh mẽ, có giấy phép thương mại (ví dụ các dòng Qwen, Code Llama, DeepSeek Coder, Starcoder, Mistral, Gemma đã được nâng cấp). *Lưu ý: Tên model cụ thể là giả định, cần nghiên cứu các model mới nhất tại thời điểm triển khai.*
* **Công cụ Phân tích Tĩnh Truyền thống:** Linters, formatters, SAST tools phù hợp với các ngôn ngữ trong dự án.
* **Ngôn ngữ phát triển Agent Điều phối:** Python (khuyến nghị do có nhiều thư viện hỗ trợ AI/LLM và hệ thống).

**IV. Tính năng & Lợi ích Nổi bật:**

* **Review Toàn diện:** Bao phủ nhiều khía cạnh từ phong cách, lỗi, bảo mật đến tối ưu hóa.
* **Tăng cường Chất lượng Code:** Giúp code sạch hơn, an toàn hơn, dễ bảo trì hơn.
* **Tiết kiệm Thời gian:** Giảm đáng kể thời gian review thủ công.
* **Phản hồi Nhanh chóng:** Giúp developer sửa lỗi sớm trong chu trình phát triển.
* **Bảo mật Tuyệt đối:** Toàn bộ code và quá trình phân tích diễn ra trên máy local.
* **Học hỏi & Nâng cao Kỹ năng:** Developer học được từ các giải thích và gợi ý của AI.
* **Tùy biến Cao:** Dễ dàng cấu hình agent, model, rule cho phù hợp với từng dự án.
* **Dễ Mở rộng:** Có thể thêm agent mới cho các khía cạnh review mới trong tương lai.

**V. Những Điểm cần Lưu ý khi Triển khai:**

* **Thiết lập Môi trường Local:** Cần đảm bảo self-hosted runner và Ollama được cài đặt, cấu hình đúng cách.
* **Tài nguyên Phần cứng:** Chạy nhiều LLM có thể yêu cầu cấu hình máy local mạnh (GPU, RAM).
* **Nghệ thuật Prompt Engineering:** Chất lượng gợi ý phụ thuộc rất nhiều vào việc thiết kế prompt cho từng agent.
* **Quản lý Cấu hình:** Duy trì hệ thống file cấu hình một cách khoa học.
* **Xây dựng Bộ Đánh giá (Evaluation Framework):** Cần có bộ test case để kiểm tra và đảm bảo chất lượng của hệ thống khi có thay đổi.

**VI. Tiềm năng Phát triển trong Tương lai:**

* **Tích hợp Sâu hơn với IDE:** Đưa gợi ý trực tiếp vào môi trường phát triển của lập trình viên.
* **Fine-tuning Model trên Codebase Riêng:** Huấn luyện thêm các model LLM trên dữ liệu code và review của chính dự án để tăng độ chính xác và phù hợp.
* **Hỗ trợ Tự động Sửa lỗi (Auto-fix) có Giám sát:** Cho phép AI đề xuất các bản vá tự động cho một số loại lỗi đơn giản, nhưng luôn cần sự phê duyệt của con người.
* **Phân tích Ảnh hưởng Liên Module (Cross-Module Impact Analysis):** Mở rộng khả năng phân tích side effect ra ngoài phạm vi file hiện tại.

**Lời kết:**
NovaGuard AI không chỉ là một công cụ, mà là một người đồng hành thông minh, giúp đội ngũ của bạn chinh phục những dòng code chất lượng cao hơn, an toàn hơn và hiệu quả hơn. Bằng cách kết hợp những gì tốt nhất của công nghệ hiện có và trí tuệ nhân tạo tiên tiến, chúng ta có thể tạo ra một cuộc cách mạng nhỏ trong quy trình phát triển phần mềm của mình.

---

### PROMPT

Chào Gemini Coding Partner,

Mục tiêu của prompt này là cung cấp cho bạn một bản thiết kế chi tiết và toàn diện để bạn có thể bắt đầu xây dựng dự án **NovaGuard AI**. Đây là một GitHub Action review code thông minh, sử dụng hệ thống Đa Agent Lai (Hybrid Multi-Agent System) kết hợp các công cụ phân tích tĩnh truyền thống với các mô hình ngôn ngữ lớn (LLM) chạy local qua Ollama.

Hãy coi đây là kim chỉ nam cho quá trình phát triển của bạn. Nếu có bất kỳ điểm nào chưa rõ, đừng ngần ngại đặt câu hỏi.

**Bối cảnh công nghệ:** Chúng ta đang ở tháng 5 năm 2025. Các lựa chọn về framework đã được cân nhắc. Các tên model LLM cụ thể mang tính minh họa và bạn nên tìm hiểu các model open source mới nhất, phù hợp nhất tại thời điểm code, nhưng chúng phải hỗ trợ chạy qua Ollama và có giấy phép cho phép sử dụng thương mại.

---

## Prompt Phát triển Dự án: NovaGuard AI

**1. Tổng quan Dự án:**

* **Tên Dự án:** NovaGuard AI
* **Loại Dự án:** GitHub Docker Container Action có thể tái sử dụng.
* **Mục đích:** Cung cấp một giải pháp review code tự động, thông minh, bảo mật (chạy local), và tùy biến cao cho các dự án trên GitHub. NovaGuard AI sẽ phân tích code trong Pull Request (PR), đưa ra các nhận xét, cảnh báo về lỗi, vấn đề bảo mật, phong cách code, và gợi ý cải thiện.
* **Công nghệ Chính:**
    * Ngôn ngữ: Python 3.10+
    * Framework LLM: Langchain & LangGraph
    * LLM Runtime: Ollama (kết nối tới Ollama server đang chạy trên self-hosted runner), có thêm option để sử dụng Gemini, OpenAI API 
    * Đóng gói Action: Docker
    * Nền tảng CI/CD: GitHub Actions
    * Định dạng Output chính: SARIF (Static Analysis Results Interchange Format) v2.1.0.

**2. Thiết kế Chi tiết Kỹ thuật:**

**I. Đóng gói GitHub Action (`action.yml`, `Dockerfile`, `src/action_entrypoint.py`)**

* **`action.yml` (Metadata File):**
    * `name`: 'NovaGuard AI Code Review'
    * `description`: 'An intelligent code review co-pilot using LLMs and traditional tools via local Ollama.'
    * `author`: (Để trống hoặc tên người phát triển)
    * `branding`: `icon: 'shield'`, `color: 'blue'`
    * `inputs`:
        * `github_token`: `{ description: 'GitHub token for GitHub API interactions (e.g., fetching PR data if needed, though SARIF upload is preferred via a separate action).', required: true, default: '${{ github.token }}' }`
        * `ollama_base_url`: `{ description: 'Base URL of the running Ollama server.', required: true, default: 'http://localhost:11434' }`
        * `project_config_path`: `{ description: 'Optional path to a project-specific NovaGuard AI config directory within the target repository (e.g., .github/novaguard_config/).', required: false }`
        * `sarif_output_file`: `{ description: 'Filename for the generated SARIF report within GITHUB_WORKSPACE.', required: false, default: 'novaguard-report.sarif' }`
        * `fail_on_severity`: `{ description: 'Minimum severity (e.g., error, warning, note) to cause the action to fail. Default is "none".', required: false, default: 'none' }`
    * `outputs`:
        * `report_summary_text`: `{ description: 'A brief text summary of review findings.' }`
        * `sarif_file_path`: `{ description: 'Workspace-relative path to the generated SARIF report file.' }`
    * `runs`: `{ using: 'docker', image: 'Dockerfile' }`

* **`Dockerfile`:**
    * Base Image: `python:3.11-slim`
    * `WORKDIR /app`
    * Cài đặt các tool CLI cần thiết (ví dụ: `semgrep`, các linter như `pylint`, `eslint`, `checkstyle` - nếu không cài qua pip). Ưu tiên cài qua `pip` nếu có thể.
    * Copy `requirements.txt`, chạy `pip install --no-cache-dir -r requirements.txt`.
    * Copy `src/` vào `/app/src/`, `config/` vào `/app/config/`.
    * Copy `src/action_entrypoint.py` vào `/app/action_entrypoint.py`.
    * `ENTRYPOINT ["python", "/app/action_entrypoint.py"]`

* **`src/action_entrypoint.py` (Điểm bắt đầu của Docker Action):**
    * **Mục đích:** Nhận input từ GitHub Action environment, điều phối toàn bộ quá trình review, và tạo output.
    * **Logic chính:**
        1.  Đọc các input từ biến môi trường (ví dụ: `os.environ.get("INPUT_OLLAMA_BASE_URL")`).
        2.  Lấy thông tin ngữ cảnh GitHub (`GITHUB_EVENT_PATH`, `GITHUB_REPOSITORY`, `GITHUB_WORKSPACE`, `GITHUB_SHA`, `GITHUB_BASE_REF`, `GITHUB_HEAD_REF`).
        3.  **Lấy Code Changes:** Sử dụng `git diff ${{ env.GITHUB_BASE_REF }} ${{ env.GITHUB_HEAD_REF }} --name-only` để lấy danh sách file thay đổi, sau đó đọc nội dung các file này từ `GITHUB_WORKSPACE`. Hoặc phân tích `diff_url` của PR. Ưu tiên phân tích các file đã thay đổi.
        4.  **Tải Cấu hình:** Gọi `ConfigLoader` để tải cấu hình mặc định từ `/app/config` và override bằng `project_config_path` nếu được cung cấp. Truyền `ollama_base_url` vào đối tượng config.
        5.  **Khởi tạo Orchestrator:** Lấy compiled LangGraph app từ `src.orchestrator.graph_definition.get_compiled_graph(config_data)`.
        6.  **Chuẩn bị Input cho Graph:** Tạo `initial_graph_input` bao gồm `SharedReviewContext` (chứa PR info, danh sách file thay đổi, nội dung file, `repo_local_path=GITHUB_WORKSPACE`) và các dữ liệu thô cần thiết.
        7.  **Chạy Orchestrator Graph:** `final_state = orchestrator_app.invoke(initial_graph_input)`.
        8.  **Xử lý Kết quả:** Lấy danh sách các phát hiện (`List[Dict]`) từ `final_state`.
        9.  **Tạo Báo cáo SARIF:** Sử dụng `SarifGenerator` để chuyển đổi danh sách phát hiện thành đối tượng JSON SARIF. Lưu file SARIF này vào `GITHUB_WORKSPACE / inputs.sarif_output_file`.
        10. **Set Action Outputs:**
            * `print(f"::set-output name=sarif_file_path::{inputs.sarif_output_file}")`
            * Tạo một tóm tắt text ngắn gọn từ các phát hiện và set output `report_summary_text`.
        11. **Kiểm tra `fail_on_severity`:** Nếu có các phát hiện với mức độ nghiêm trọng bằng hoặc cao hơn `inputs.fail_on_severity`, thì `sys.exit(1)` để Action fail.

**II. Core Orchestration (LangGraph - trong `src/orchestrator/`)**

* **`state.py` - `GraphState(TypedDict)`:**
    * `shared_context: SharedReviewContext`
    * `files_to_review: List[Dict]` (ví dụ: `[{'path': str, 'content': str, 'diff_hunks': Optional[List[str]]}]`)
    * `tier1_tool_results: Dict[str, List[Dict]]` (key là tên tool, value là list kết quả của tool đó)
    * `agent_findings: List[Dict]` (danh sách tất cả các phát hiện từ các agent LLM)
    * `sarif_report_data: Optional[Dict]` (Đối tượng JSON SARIF cuối cùng)
    * `error_messages: List[str]`

* **`nodes.py` - Các hàm Node cho LangGraph:** (Mỗi hàm nhận `GraphState`, trả về `Dict` để cập nhật state)
    * **`prepare_review_files_node(state: GraphState) -> Dict:`**: Dựa trên `shared_context` (thông tin diff từ GitHub), xác định danh sách các file cần review và nội dung của chúng. Cập nhật `files_to_review`.
    * **`run_tier1_tools_node(state: GraphState) -> Dict:`**: Với mỗi file trong `files_to_review`, chạy các tool truyền thống (linters, SAST cơ bản như Semgrep với rule nhẹ) đã được cấu hình trong `tools.yml` thông qua `ToolRunner`. Lưu kết quả vào `tier1_tool_results`.
    * **`activate_style_guardian_node(state: GraphState) -> Dict:`**: Gọi `StyleGuardianAgent`. Input là các file và kết quả linter từ `tier1_tool_results`. Thêm kết quả vào `agent_findings`.
    * **`activate_bug_hunter_node(state: GraphState) -> Dict:`**: Gọi `BugHunterAgent`. Input là các file. Thêm kết quả vào `agent_findings`.
    * **`activate_securi_sense_node(state: GraphState) -> Dict:`**: Gọi `SecuriSenseAgent`. Input là các file và kết quả SAST từ `tier1_tool_results`. Thêm kết quả vào `agent_findings`.
    * **`activate_opti_tune_node(state: GraphState) -> Dict:`**: Gọi `OptiTuneAgent`. Input là các file. Thêm kết quả vào `agent_findings`.
    * **`(Optional) run_meta_review_node(state: GraphState) -> Dict:`**: Gọi `MetaReviewerAgent` để lọc, ưu tiên và tinh chỉnh `agent_findings`.
    * **`generate_sarif_report_node(state: GraphState) -> Dict:`**: Gọi `SarifGenerator` để chuyển đổi `tier1_tool_results` và `agent_findings` (đã được chuẩn hóa) thành một báo cáo SARIF. Cập nhật `sarif_report_data`.

* **`graph_definition.py` - `get_compiled_graph(config_data: Config) -> CompiledGraph:`**:
    * Khởi tạo `StateGraph(GraphState)`.
    * Thêm các node đã định nghĩa.
    * **Entry Point:** `prepare_review_files_node`.
    * **Edges:**
        * `prepare_review_files_node` -> `run_tier1_tools_node`.
        * `run_tier1_tools_node` -> (điểm bắt đầu của các agent, có thể chạy song song nếu độc lập, hoặc tuần tự). Cân nhắc việc các agent chỉ hoạt động trên các file phù hợp với ngôn ngữ của chúng.
        * Các agent node -> `run_meta_review_node` (nếu có) -> `generate_sarif_report_node`.
    * **Conditional Edges:** Có thể dùng để bỏ qua một số agent nếu không có file phù hợp hoặc dựa trên cấu hình.
    * Compile graph và trả về.

**III. Specialized Hybrid Agents (trong `src/agents/`)**

* Mỗi agent là một class, ví dụ `StyleGuardianAgent`.
* **`__init__(self, config: Config, ollama_client: OllamaClientWrapper, prompt_manager: PromptManager, tool_runner: Optional[ToolRunner] = None)`**.
* **`review(self, files_data: List[Dict], tool_outputs_for_agent: Optional[List[Dict]] = None) -> List[Dict]:`**:
    * `files_data`: danh sách các file (`{'path': str, 'content': str, 'language': str}`).
    * `tool_outputs_for_agent`: kết quả từ các tool liên quan đến agent này (ví dụ, output của Pylint cho StyleGuardian).
    * **Logic:**
        1.  Lặp qua `files_data`.
        2.  **Tích hợp Tool:** Nếu có `tool_outputs_for_agent`, sử dụng chúng.
        3.  **LLM Interaction:**
            * Xây dựng prompt (sử dụng `PromptManager`) dựa trên nội dung file, output của tool (nếu có), ngôn ngữ, và các yêu cầu cụ thể của agent.
            * Gọi `ollama_client.invoke(prompt, model_name=self.config.get_model_for_agent(self.agent_name))`.
            * Phân tích output của LLM (kỳ vọng là JSON hoặc markdown có cấu trúc).
            * Chuyển đổi thành một cấu trúc dictionary chuẩn cho mỗi "phát hiện" (finding), bao gồm: `file_path`, `line_start`, `line_end`, `message_text`, `level` (error, warning, note - theo SARIF), `rule_id` (tên agent + mã lỗi), `code_snippet_suggestion` (nếu có).
        4.  Trả về `List[Dict]` các phát hiện.

* **Cụ thể cho từng Agent:**
    * **`StyleGuardianAgent`:** Sử dụng output từ linters (Pylint, ESLint, Checkstyle...). LLM giải thích, gợi ý sửa lỗi phức tạp, tìm vấn đề phong cách khác.
    * **`BugHunterAgent`:** LLM tập trung tìm lỗi logic, null pointers, resource leaks, side effects.
    * **`SecuriSenseAgent`:** Sử dụng output từ SAST tools (Semgrep...). LLM giúp lọc false positives, giải thích, gợi ý vá lỗi, tìm mẫu mới (cẩn trọng).
    * **`OptiTuneAgent`:** LLM tìm điểm nghẽn hiệu năng, gợi ý tối ưu, dùng feature mới của ngôn ngữ.
    * **`(Optional) MetaReviewerAgent`:** LLM nhận tất cả `agent_findings`, lọc trùng lặp, đánh giá độ tin cậy, tổng hợp.

**IV. Core Utility Modules (trong `src/core/`)**

* **`config_loader.py` - `Config` class & `load_config()`:**
    * Tải `models.yml` (tên model Ollama cho từng agent/task), `tools.yml` (command, args cho Pylint, Semgrep...).
    * Tải prompt templates từ `config/prompts/`.
    * Lưu trữ `ollama_base_url`.
* **`ollama_client.py` - `OllamaClientWrapper`:**
    * Kết nối tới `ollama_base_url`.
    * Phương thức `invoke(prompt: str, model_name: str, system_message: Optional[str] = None, temperature: float = 0.5, ...) -> str`.
* **`tool_runner.py` - `ToolRunner`:**
    * Phương thức `run(tool_name: str, file_path: str, project_root: str) -> Dict:` (trả về output đã parse, ví dụ JSON nếu tool hỗ trợ, hoặc text thô). Cần xử lý `cwd` và các tham số dòng lệnh.
* **`sarif_generator.py` - `SarifGenerator` class hoặc functions:**
    * Phương thức `add_finding(self, file_path: str, line_start: int, message_text: str, rule_id: str, level: str, ...)`.
    * Phương thức `get_sarif_report() -> Dict:` (trả về đối tượng JSON SARIF hoàn chỉnh). Tuân thủ schema SARIF v2.1.0.
* **`prompt_manager.py` - `PromptManager`:**
    * `get_prompt(prompt_name: str, variables: Dict) -> str` (sử dụng Jinja2 templates).
* **`shared_context.py` - `SharedReviewContext(BaseModel)` (Pydantic model):**
    * Định nghĩa rõ ràng cấu trúc dữ liệu này (PR URL, diff content, list files/content, repo_local_path, etc.).

**V. Hệ thống Cấu hình (trong `config/`)**

* **`models.yml`:**
    ```yaml
    agents:
      style_guardian: "codellama:13b-instruct-q5_K_M" # Tên model trên Ollama
      bug_hunter: "deepseek-coder:33b-instruct-q4_K_M"
      # ...
    meta_reviewer: "mistral:7b-instruct-v0.2-q5_K_M"
    ```
* **`tools.yml`:**
    ```yaml
    linters:
      python: "pylint --output-format=json --rcfile={project_root}/.pylintrc {file_path}"
      # javascript: "eslint -f json -c {project_root}/.eslintrc.js {file_path}"
    sast:
      generic: "semgrep scan --config auto --json --output {output_file} {project_root}"
    ```
* **`prompts/` directory:** Chứa các file template (ví dụ: `style_guardian_python.md`).

**VI. Xử lý Lỗi và Logging:**

* Sử dụng `logging` module của Python.
* Các node trong LangGraph nên bắt lỗi và cập nhật `error_messages` trong `GraphState`.
* `action_entrypoint.py` nên log các bước chính và output các lỗi ra stdout/stderr để GitHub Actions hiển thị.

**3. Ghi chú Phát triển và Kiểm thử:**

* Viết unit test cho các utility function, logic phân tích output của LLM, và các phần quan trọng của agent.
* Tạo workflow `test_action.yml` trong `.github/workflows/` để build Docker image và chạy action trên một PR mẫu trong chính repo NovaGuard AI.
* Thiết lập một quy trình kiểm thử local (ví dụ, một script `run_local.py` mô phỏng `action_entrypoint.py` với dữ liệu mẫu) để tăng tốc độ phát triển.
* Tập trung vào việc làm cho output của LLM có cấu trúc (JSON) để dễ parse.

**4. Workflow Ví dụ cho Người dùng (trong README.md của NovaGuard AI):**

```yaml
name: NovaGuard AI Code Review

on: pull_request

permissions:
  contents: read
  security-events: write # Để upload SARIF

jobs:
  novaguard_review:
    runs-on: self-hosted # Runner này PHẢI cài Ollama và có các model cần thiết
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4
        with: { fetch-depth: 0 } # Lấy full history để git diff hoạt động đúng

      - name: Run NovaGuard AI
        uses: YOUR_USERNAME/novaguard_ai@v1 # Thay bằng repo của bạn
        id: novaguard
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          ollama_base_url: 'http://your-ollama-server-address:11434'
          # project_config_path: '.github/novaguard_config' # Tùy chọn
          sarif_output_file: 'results/novaguard.sarif'
          # fail_on_severity: 'warning' # Tùy chọn

      - name: Upload SARIF to GitHub Code Scanning
        if: success() || failure() # Chạy ngay cả khi step trước fail (để upload report)
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: ${{ steps.novaguard.outputs.sarif_file_path }}
          category: 'NovaGuardAI'
```

**5. Lời nhắn cuối cùng cho Gemini Coding Partner:**

Bản thiết kế này là một khung sườn chi tiết. Trong quá trình code, bạn có thể sẽ gặp những quyết định nhỏ cần đưa ra. Hãy ưu tiên sự rõ ràng, module hóa, và khả năng bảo trì. Nếu cần thiết kế lại một phần nhỏ để tối ưu hơn, hãy đề xuất. 
LƯU Ý: 
- Khi tạo cấu trúc project vui lòng tạo bash file đính kèm để tạo list folder/file nhanh hơn (Tôi đã tạo folder NOVAGUARD-AI) rồi.
- Viết code lần lượt và ĐẦY ĐỦ ngay từ đầu.
Chúc may mắn và hãy tạo ra một NovaGuard AI thật ấn tượng!

--- 
## Update:

Tuyệt vời! Việc NovaGuard AI đã hoạt động cơ bản trên GitHub Actions là một thành tựu lớn! Giờ là lúc chúng ta suy nghĩ về việc cải thiện và mở rộng hệ thống.

Dựa trên thiết kế ban đầu và những gì chúng ta đã xây dựng, đây là một số ý tưởng nâng cấp tiềm năng, chia theo các hạng mục:

**I. Cải thiện Chất lượng Review và Độ chính xác của Agent:**

1.  **Tinh chỉnh Prompt Chuyên sâu (Prompt Engineering):**
    * **Thử nghiệm nhiều biến thể prompt:** Với mỗi agent, thử các cách diễn đạt khác nhau, thay đổi lượng context, và cấu trúc output yêu cầu để xem model nào phản hồi tốt nhất với prompt nào.
    * **Chain-of-Thought (CoT) / Reasoning Steps:** Yêu cầu LLM giải thích các bước suy luận của nó *trước khi* đưa ra finding cuối cùng. Điều này có thể cải thiện độ chính xác, đặc biệt với BugHunter và SecuriSense. Bạn có thể yêu cầu LLM output phần giải thích này (để debug) hoặc chỉ dùng nó như một bước trung gian.
    * **Few-Shot Learning trong Prompt:** Cung cấp một vài ví dụ (examples) về code tốt/xấu và finding mong muốn ngay trong prompt để "hướng dẫn" LLM tốt hơn, đặc biệt cho các lỗi phức tạp hoặc đặc thù của dự án.
    * **Prompt theo Ngữ cảnh Pull Request:** Tận dụng thêm thông tin từ PR (tiêu đề, mô tả, các comment trước đó nếu có) để cung cấp ngữ cảnh rộng hơn cho LLM.

2.  **Nâng cấp MetaReviewerAgent (Nếu được kích hoạt):**
    * **Confidence Scoring:** Yêu cầu các agent LLM tự đánh giá độ tin cậy (confidence score) cho mỗi finding của chúng. MetaReviewer có thể sử dụng điểm này để lọc hoặc ưu tiên.
    * **Cross-Agent Reasoning:** Thiết kế prompt cho MetaReviewer để nó không chỉ lọc trùng lặp mà còn cố gắng tìm ra mối liên hệ giữa các finding từ các agent khác nhau (ví dụ: một lỗi style có thể làm tăng nguy cơ một lỗi logic).
    * **Học từ Feedback (Nâng cao):** Nếu có cách thu thập phản hồi của người dùng về chất lượng finding (ví dụ, qua comment trên PR hoặc một cơ chế khác), MetaReviewer có thể được huấn luyện (fine-tune) hoặc được cung cấp các ví dụ phản hồi đó trong prompt để cải thiện.

3.  **Xử lý False Positives và False Negatives:**
    * **False Positives (Báo sai):**
        * Cải thiện prompt để LLM cẩn trọng hơn, yêu cầu giải thích rõ ràng hơn.
        * Cho phép người dùng đánh dấu finding là "false positive" (ví dụ qua comment trên PR với tag đặc biệt), và có thể đưa thông tin này vào các lần review sau cho cùng một đoạn code.
    * **False Negatives (Bỏ sót):**
        * Thử nghiệm các model LLM lớn hơn hoặc chuyên biệt hơn cho từng agent.
        * Bổ sung thêm các rule cho tool truyền thống (ví dụ, Semgrep ruleset tùy chỉnh).

4.  **Sử dụng Tool Output Hiệu quả hơn:**
    * **Chuẩn hóa sâu hơn output của tool:** Đảm bảo rằng output từ Pylint, Semgrep, và các tool khác được chuẩn hóa thành một cấu trúc dữ liệu thật chi tiết và nhất quán trước khi đưa vào prompt cho LLM hoặc vào `SarifGenerator`. Điều này giúp LLM dễ "tiêu hóa" hơn.
    * **Trích xuất thông tin cụ thể từ tool:** Thay vì chỉ đưa message text, cố gắng trích xuất mã lỗi (rule ID), loại lỗi, severity từ tool để LLM có thể tham chiếu chính xác hơn.

**II. Mở rộng Chức năng và Tính Năng:**

5.  **Thêm Agent Mới:**
    * **DocumentationGuardian:** Kiểm tra xem code có comment và tài liệu (docstrings) đầy đủ, rõ ràng, và cập nhật không.
    * **TestCoverageAssessor:** (Phức tạp hơn) Phân tích code thay đổi và gợi ý các test case còn thiếu hoặc cần cập nhật (có thể dựa trên việc LLM hiểu logic code).
    * **DependencyChecker:** (Kết hợp tool) Kiểm tra các thư viện sử dụng có lỗ hổng bảo mật đã biết (ví dụ qua `pip-audit` hoặc tích hợp Snyk/Dependabot-like tool output).
    * **AccessibilityLinter (cho Frontend):** Nếu dự án có frontend, thêm agent/tool để kiểm tra các vấn đề về accessibility (a11y).

6.  **Tích hợp Comment trực tiếp vào PR:**
    * Như đã thảo luận, hiện tại action đang dựa vào việc upload SARIF. Bạn có thể nâng cấp `action_entrypoint.py` để:
        * Sau khi có SARIF report, tóm tắt các finding quan trọng nhất (ví dụ, các lỗi "error" hoặc "warning").
        * Sử dụng GitHub API (với `github_token`) để đăng một comment lên Pull Request với tóm tắt đó.
        * **Thư viện/Action hỗ trợ:** Có thể dùng thư viện `PyGithub` trong Python hoặc action như `peter-evans/create-or-update-comment` để đơn giản hóa việc này.
        * **Lưu ý:** Cần thêm quyền `pull-requests: write` cho workflow.

7.  **Hỗ trợ Auto-Fix (Có giám sát):**
    * Với một số lỗi đơn giản (ví dụ, lỗi style, import không dùng), LLM có thể đề xuất trực tiếp đoạn code sửa lỗi.
    * Action có thể tạo ra một suggestion patch (diff format) và comment nó vào PR, cho phép người dùng dễ dàng chấp nhận và commit. GitHub có API cho việc này.
    * **Cảnh báo:** Tính năng này cần được thực hiện cẩn thận và luôn cần sự review của con người trước khi áp dụng.

8.  **Cấu hình Linh hoạt hơn cho Rule và Severity Mapping:**
    * Cho phép người dùng định nghĩa cách map severity của tool/LLM sang SARIF level trong file config của dự án.
    * Cho phép người dùng bỏ qua (ignore) một số rule cụ thể của tool hoặc agent trong file config của dự án.

**III. Cải thiện Hiệu năng và Trải nghiệm Người dùng:**

9.  **Tối ưu hóa Thời gian Chạy:**
    * **Chạy song song các Agent (Nếu độc lập):** LangGraph hỗ trợ chạy các node song song nếu chúng không phụ thuộc vào output của nhau. Ví dụ, StyleGuardian, BugHunter, SecuriSense, OptiTune có thể chạy song song sau khi có `files_to_review` và `tier1_tool_results`.
    * **Caching thông minh hơn:**
        * Cache kết quả review cho các file không thay đổi giữa các lần commit trong cùng một PR (nếu có thể).
        * Cache các lệnh gọi LLM nếu prompt và context không đổi (LangChain có hỗ trợ caching).
    * **Chọn model tối ưu:** Sử dụng các model nhỏ hơn, nhanh hơn cho các tác vụ không quá phức tạp nếu chất lượng vẫn đảm bảo.

10. **Logging và Debugging Tốt hơn:**
    * Thêm tùy chọn log level chi tiết hơn (ví dụ, qua input của action).
    * Log rõ ràng input/output của từng node trong LangGraph, và từng lời gọi LLM (có thể có option để ẩn nội dung code nhạy cảm).
    * Nếu có thể, tích hợp với LangSmith để theo dõi và debug các chain/graph của LangChain.

11. **Cải thiện Output SARIF:**
    * Đảm bảo tất cả các trường quan trọng của SARIF được điền đầy đủ và chính xác (ví dụ: `rule.helpUri`, `result.codeFlows` nếu có).
    * Sử dụng `partialFingerprints` để giúp GitHub nhóm các lỗi tương tự tốt hơn.

**IV. Mở rộng Khả năng Tích hợp:**

12. **Hỗ trợ thêm LLM Provider (Ngoài Ollama):**
    * Như trong thiết kế ban đầu, bạn có thể thêm option để kết nối đến API của OpenAI, Gemini, Anthropic, etc. Điều này yêu cầu sửa `OllamaClientWrapper` (hoặc tạo các client riêng) và thêm cấu hình model tương ứng.

13. **Web UI (Nâng cao, ngoài phạm vi GitHub Action):**
    * Nếu muốn, bạn có thể xây dựng một Web UI riêng để hiển thị lịch sử review, thống kê, cấu hình rule, v.v. Action có thể gửi dữ liệu đến một backend API cho UI này.

**Bắt đầu từ đâu?**

Với nhiều ý tưởng như vậy, đây là một vài gợi ý về thứ tự ưu tiên:

1.  **Ưu tiên hàng đầu: Hoàn thiện và ổn định chất lượng parsing JSON từ LLM.** Đây là nền tảng. Nếu LLM trả về cấu trúc khác nữa, bạn cần có cơ chế xử lý linh hoạt hoặc prompt mạnh mẽ hơn.
    * In ra toàn bộ `response_text` của **tất cả các agent** để xem output thô của `qwen2.5:7b` (hoặc model bạn chọn) cho từng loại prompt.
    * Điều chỉnh logic parsing trong từng agent cho phù hợp với output thực tế đó.

2.  **Tinh chỉnh Prompt:** Sau khi parse được JSON, hãy tập trung vào việc cải thiện chất lượng nội dung của các finding bằng cách tinh chỉnh prompt.
3.  **Tích hợp Comment trực tiếp vào PR:** Đây là một tính năng giá trị cao cho người dùng.
4.  **Tối ưu hóa thời gian chạy:** Xem xét việc chạy song song các agent độc lập.

Hãy chọn một vài điểm bạn thấy hứng thú và quan trọng nhất để bắt đầu. Chúc bạn thành công với việc nâng cấp NovaGuard AI!