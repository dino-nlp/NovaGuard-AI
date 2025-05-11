# Design NOVAGUARD AI 2.0

## Bản Thiết kế Dự án: NovaGuard-AI 2.0 – Nền tảng Phân tích Code Thông minh và Chuyên sâu

**Phiên bản:** 2.0
**Ngày cập nhật:** 12 tháng 5 năm 2025
**Định hướng chính:** Chuyển đổi từ GitHub Action sang một nền tảng website độc lập, cung cấp khả năng phân tích code chuyên sâu, hiểu biết toàn diện về dự án, và tận dụng tối đa sức mạnh của LLM để đưa ra những insight giá trị, khác biệt.

**I. Tổng quan và Tầm nhìn**

NovaGuard-AI 2.0 là một nền tảng website tiên tiến, được thiết kế để trở thành người đồng hành không thể thiếu của các đội nhóm phát triển phần mềm. Mục tiêu của NovaGuard-AI 2.0 là cung cấp những phân tích code tự động, thông minh, và chuyên sâu vượt xa các công cụ review truyền thống. Bằng cách hiểu toàn bộ ngữ cảnh của một dự án – từ kiến trúc tổng thể, luồng logic nghiệp vụ, đến các coding convention đặc thù – NovaGuard-AI 2.0 giúp phát hiện các vấn đề tiềm ẩn, cải thiện chất lượng thiết kế, nâng cao khả năng bảo trì, và giảm thiểu rủi ro trong quá trình phát triển phần mềm.

**II. Đối tượng Người dùng Mục tiêu**

* **Đội nhóm Phát triển Phần mềm:** (Mọi quy mô) Tìm kiếm công cụ review code tự động hiệu quả, giảm thời gian review thủ công, nâng cao chất lượng code.
* **Kiến trúc sư Phần mềm & Tech Leads:** Cần công cụ để đánh giá và duy trì sự tuân thủ kiến trúc, phát hiện sớm các "architectural smells" và nợ kỹ thuật.
* **Nhà Quản lý Kỹ thuật/Sản phẩm:** Muốn theo dõi "sức khỏe" code của dự án, chất lượng đầu ra của đội ngũ, và đưa ra quyết định dựa trên dữ liệu.
* **Lập trình viên Cá nhân:** Muốn nhận được những phản hồi sâu sắc để cải thiện kỹ năng và chất lượng code cá nhân.

**III. Kiến trúc Hệ thống Tổng thể**

NovaGuard-AI 2.0 sẽ được xây dựng theo kiến trúc microservices hoặc module hóa cao để đảm bảo khả năng mở rộng và bảo trì.

1.  **Frontend (Ứng dụng Web Đơn Trang - SPA):**
    * Giao diện người dùng chính, nơi người dùng tương tác với hệ thống.
    * Chức năng: Đăng ký/Đăng nhập, quản lý profile, thêm/quản lý dự án, xem dashboard, cấu hình dự án, xem chi tiết báo cáo phân tích, tương tác với kết quả review.
    * Công nghệ gợi ý: React/Vue/Angular với TypeScript.

2.  **Backend API Gateway:**
    * Điểm vào duy nhất cho tất cả các yêu cầu từ frontend.
    * Chức năng: Xác thực request, định tuyến đến các service phù hợp, tổng hợp response.
    * Công nghệ gợi ý: FastAPI (Python), NestJS (Node.js).

3.  **Core Analysis Engine (Hệ thống Phân tích Lõi – Backend):**
    * **Project Manager Service:**
        * Xử lý việc kết nối với các nền tảng quản lý source code (ban đầu là GitHub).
        * Lấy thông tin dự án, clone/fetch source code.
        * Quản lý thông tin xác thực (ví dụ: GitHub App tokens).
    * **Webhook Handler Service:**
        * Tiếp nhận và xử lý các sự kiện webhook từ GitHub (ví dụ: PR được tạo/cập nhật, push lên nhánh chính).
        * Kích hoạt các tác vụ phân tích tương ứng.
    * **Analysis Orchestrator Service (Dựa trên LangGraph & MCP):**
        * "Bộ não" điều phối toàn bộ quy trình phân tích code.
        * Quản lý `DynamicProjectContext` và `Code Knowledge Graph (CKG)`.
        * Bao gồm các node chính:
            * `InitializeContextNode`: Khởi tạo `DynamicProjectContext` ban đầu.
            * `CodeGraphBuilderNode`: Xây dựng và cập nhật CKG từ source code.
            * `ContextEnrichmentNode`: Làm giàu `DynamicProjectContext` bằng thông tin từ CKG, cấu hình dự án, và các nguồn khác.
            * Các **Agent Chuyên sâu** (xem mục VI).
            * `MetaReviewerAgent`: Tổng hợp, lọc, và ưu tiên các phát hiện từ các agent, sử dụng `DynamicProjectContext` để đánh giá.
            * `ReportGeneratorService`: Tạo các báo cáo phân tích chi tiết cho frontend.
    * **LLM Service Wrapper:**
        * Giao tiếp với các LLM (ban đầu là Ollama chạy local, có thể mở rộng sang các API như Gemini, OpenAI nếu người dùng cấu hình).
        * Quản lý prompt, retry, xử lý lỗi.
    * **Static Analysis Tools Integrator:**
        * Tích hợp và thực thi các công cụ phân tích tĩnh truyền thống (linters, SAST tools). Kết quả từ các tool này sẽ là một phần đầu vào cho `ContextEnrichmentNode` và các agent LLM.

4.  **Data Persistence Layer (Lớp Lưu trữ Dữ liệu):**
    * **Relational Database (ví dụ: PostgreSQL):**
        * Lưu trữ thông tin người dùng, dự án, cấu hình dự án, tóm tắt kết quả review, trạng thái tác vụ phân tích, lịch sử webhook.
    * **Graph Database (Ví dụ: Neo4j - Rất khuyến khích cho CKG):**
        * Lưu trữ và cho phép truy vấn hiệu quả Code Knowledge Graph (CKG) của các dự án.
    * **Vector Database (Ví dụ: ChromaDB, Weaviate):**
        * Lưu trữ semantic embeddings của các đoạn code, file, module để hỗ trợ tìm kiếm ngữ nghĩa và làm giàu context.
    * **Object Storage (Ví dụ: MinIO, AWS S3):**
        * Lưu trữ các file source code đã clone, các báo cáo SARIF (nếu vẫn dùng), các file log lớn, cache dữ liệu phân tích.

5.  **Job Queue & Worker System (Hàng đợi Tác vụ & Hệ thống Worker):**
    * **Message Queue (Ví dụ: RabbitMQ, Kafka):**
        * Quản lý các tác vụ phân tích code (đặc biệt là "Scan Toàn bộ Dự án" và "Review PR" có thể tốn thời gian) để xử lý bất đồng bộ, tránh block request từ người dùng.
    * **Worker Processes:**
        * Các tiến trình độc lập (có thể scale) lắng nghe tác vụ từ message queue và thực thi các pipeline của `Analysis Orchestrator Service`.

6.  **Authentication & Authorization Service:**
    * Quản lý việc đăng ký, đăng nhập (hỗ trợ đăng nhập qua GitHub OAuth).
    * Quản lý quyền truy cập của người dùng đối với các dự án và tính năng.

**IV. Model Context Protocol (MCP) và Code Knowledge Graph (CKG)**

Đây là hai thành phần cốt lõi giúp NovaGuard-AI 2.0 hiểu sâu về dự án:

1.  **`DynamicProjectContext` (Pydantic Model hoặc tương đương):**
    * Một đối tượng động, chứa toàn bộ thông tin ngữ cảnh liên quan đến một phiên phân tích cụ thể (cho PR hoặc toàn bộ dự án).
    * Bao gồm: Thông tin PR/commit, danh sách file thay đổi, nội dung file, metadata dự án, cấu trúc thư mục, tóm tắt các module quan trọng, coding conventions, design patterns của dự án (từ cấu hình hoặc suy luận), thông tin từ CKG, các phát hiện từ agent trước đó.
    * Được khởi tạo bởi `InitializeContextNode` và làm giàu liên tục bởi `ContextEnrichmentNode` và `CodeGraphBuilderNode`.

2.  **Code Knowledge Graph (CKG):**
    * Một biểu đồ tri thức biểu diễn các thực thể trong source code (files, classes, functions, methods, variables, interfaces, modules, API endpoints, database schemas, data flows, business logic units...) và các mối quan hệ đa dạng giữa chúng (gọi, kế thừa, hiện thực hóa, sử dụng, sửa đổi, phụ thuộc, tạo ra, tiêu thụ...).
    * **Xây dựng và Cập nhật:**
        * Sử dụng kết hợp AST parsing (ví dụ: `tree-sitter`), phân tích luồng dữ liệu tĩnh, và có thể cả LLM để trích xuất thực thể và mối quan hệ.
        * CKG nền tảng được xây dựng khi "Scan Toàn bộ Dự án" và được cập nhật gia tăng khi có thay đổi mới (ví dụ: qua PR).
    * **Lưu trữ:** Ưu tiên Graph Database (Neo4j) để truy vấn hiệu quả.
    * **Sử dụng:** Các agent chuyên sâu sẽ truy vấn CKG để hiểu rõ hơn về tác động của thay đổi, luồng dữ liệu, các phụ thuộc ẩn, và ngữ cảnh kiến trúc.

3.  **Semantic Code Embeddings:**
    * Các đoạn code, function, class, file sẽ được nhúng thành vector ngữ nghĩa.
    * Lưu trữ trong Vector Database.
    * Sử dụng để tìm kiếm các đoạn code tương tự, các module liên quan về mặt ngữ nghĩa, giúp làm giàu `DynamicProjectContext` và hỗ trợ các agent.

**V. Các Tính năng Chính của Nền tảng Website NovaGuard-AI 2.0**

1.  **Quản lý Người dùng & Xác thực:**
    * Đăng ký tài khoản mới.
    * Đăng nhập (email/password và tùy chọn "Sign in with GitHub").
    * Quản lý thông tin cá nhân.

2.  **Quản lý Dự án:**
    * **Thêm Dự án Mới:**
        * Kết nối với tài khoản GitHub của người dùng.
        * Cho phép chọn repository (private hoặc public nếu được cấp quyền).
        * Chọn nhánh chính để theo dõi.
        * (Sau khi thêm) NovaGuard-AI sẽ thực hiện một lần "Scan Toàn bộ Dự án" ban đầu để xây dựng CKG nền tảng.
    * **Dashboard Dự án:**
        * Hiển thị tổng quan "sức khỏe" code (ví dụ: điểm chất lượng, số lượng vấn đề nghiêm trọng, xu hướng theo thời gian).
        * Danh sách các Pull Request gần đây và trạng thái review của NovaGuard-AI.
        * Lịch sử các lần "Scan Toàn bộ Dự án".
        * Truy cập nhanh vào cấu hình dự án.

3.  **Tính năng "Scan Toàn bộ Dự án" (Full Project Scan):**
    * **Kích hoạt:** Người dùng có thể trigger thủ công bất cứ lúc nào hoặc thiết lập lịch quét định kỳ (ví dụ: hàng đêm, hàng tuần).
    * **Quy trình:**
        1.  Checkout/Fetch phiên bản mới nhất của nhánh chính.
        2.  `CodeGraphBuilderNode` xây dựng hoặc cập nhật toàn bộ CKG của dự án.
        3.  `ContextEnrichmentNode` làm giàu `DynamicProjectContext` cho toàn bộ dự án.
        4.  Tất cả các **Agent Chuyên sâu** được kích hoạt để phân tích toàn bộ codebase dựa trên CKG và `DynamicProjectContext`.
        5.  `ReportGeneratorService` tạo báo cáo tổng thể.
    * **Hiển thị Báo cáo:**
        * Các vấn đề kiến trúc lớn (ví dụ: vi phạm SOLID, module quá lớn, coupling cao).
        * Danh sách nợ kỹ thuật (technical debt) được định lượng và ưu tiên.
        * Các "hotspot" về lỗi tiềm ẩn, lỗ hổng bảo mật, vấn đề hiệu năng trên toàn dự án.
        * (Nâng cao) Giao diện trực quan hóa một phần CKG, làm nổi bật các khu vực có vấn đề.

4.  **Tính năng "Review Pull Request Tự động" (Automated PR Review):**
    * **Kích hoạt:** Tự động khi có PR mới được tạo hoặc cập nhật trên GitHub (thông qua webhook).
    * **Quy trình:**
        1.  Webhook Handler nhận sự kiện, gửi tác vụ vào Message Queue.
        2.  Worker lấy thông tin PR, code diff.
        3.  `CodeGraphBuilderNode` cập nhật CKG một cách gia tăng cho các phần code bị thay đổi và các thành phần liên quan trực tiếp (sử dụng CKG nền tảng đã có).
        4.  `ContextEnrichmentNode` xây dựng `DynamicProjectContext` cho phạm vi PR, dựa trên diff và thông tin từ CKG.
        5.  Các **Agent Chuyên sâu** được kích hoạt để phân tích các thay đổi trong PR và tác động của chúng.
        6.  `ReportGeneratorService` tạo báo cáo chi tiết cho PR.
    * **Hiển thị Báo cáo và Tích hợp GitHub:**
        * Kết quả review chi tiết được hiển thị trên một trang riêng của PR đó trên website NovaGuard-AI.
        * Một comment tóm tắt (với link đến báo cáo chi tiết) được tự động đăng lên PR trên GitHub.
        * (Tùy chọn) Cập nhật status check của PR trên GitHub.

5.  **Trang Chi tiết Review/Phát hiện:**
    * Mô tả chi tiết vấn đề được phát hiện.
    * Đoạn code liên quan được highlight.
    * Giải thích rõ ràng "Tại sao" đây là một vấn đề (dựa trên CKG, nguyên lý thiết kế, coding convention của dự án, hoặc suy luận của LLM).
    * Gợi ý các giải pháp khắc phục, có thể kèm theo ví dụ code.
    * Hiển thị "Dấu vết Suy luận" (Reasoning Trace) của LLM (nếu có, giúp tăng tính minh bạch).
    * Chức năng cho người dùng:
        * Thêm bình luận, thảo luận.
        * Đánh dấu: "Đã giải quyết", "Sai (False Positive)", "Sẽ xem xét sau".
        * Cung cấp phản hồi về chất lượng của gợi ý.

6.  **Quản lý Cấu hình Dự án (qua Giao diện Web):**
    * Chọn/Cấu hình các model LLM cho từng agent hoặc tác vụ.
    * Bật/Tắt các Agent phân tích.
    * Định nghĩa các Coding Conventions và Architectural Rules riêng của dự án (ví dụ: "Không cho phép circular dependencies giữa các module X, Y, Z", "Tất cả các service phải implement interface LoggingService"). Các quy tắc này sẽ được MCP và các agent sử dụng.
    * Thiết lập "Độ sâu" và "Phạm vi" phân tích (ví dụ: các chế độ "Nhanh & Tập trung PR", "Cân bằng", "Sâu & Toàn diện").
    * Quản lý danh sách các tool phân tích tĩnh tích hợp và cấu hình của chúng.

7.  **(Nâng cao) Theo dõi Nợ Kỹ thuật (Technical Debt Tracking):**
    * NovaGuard-AI có thể giúp nhận diện, phân loại, và ước tính nợ kỹ thuật.
    * Dashboard hiển thị xu hướng nợ kỹ thuật theo thời gian.

8.  **(Nâng cao) Knowledge Base Riêng cho Dự án:**
    * Cho phép người dùng lưu trữ các quyết định thiết kế quan trọng, lý do tại sao một số cảnh báo được coi là false positive trong ngữ cảnh dự án của họ.
    * MCP và các agent có thể tham khảo knowledge base này để đưa ra phân tích phù hợp hơn.

**VI. Các Agent Chuyên sâu trong NovaGuard-AI 2.0**

Các agent này sẽ là trái tim của khả năng phân tích chuyên sâu, tận dụng `DynamicProjectContext` và CKG.

1.  **`DeepLogicBugHunterAI`:**
    * **Nhiệm vụ:** Phát hiện các lỗi logic phức tạp, race conditions, deadlocks, null pointer exceptions tinh vi, resource leaks, các vấn đề về quản lý state, lỗi trong xử lý bất đồng bộ, và các lỗi chỉ xuất hiện khi có sự tương tác phức tạp giữa nhiều thành phần (dựa trên CKG).
    * **Kỹ thuật:** Sử dụng LLM với prompt được thiết kế để suy luận sâu về luồng thực thi, các trường hợp biên, và tương tác dữ liệu. Có thể sử dụng CoT/ToT.

2.  **`ArchitecturalAnalystAI`:**
    * **Nhiệm vụ:** Phân tích các vấn đề về thiết kế và kiến trúc phần mềm.
        * Vi phạm các nguyên lý thiết kế phổ quát (SOLID, DRY, GRASP...).
        * Phát hiện các architectural smells và anti-patterns (ví dụ: God Class/Module, Spaghetti Code, Lava Flow, Data Clumps, Feature Envy) trong ngữ cảnh cụ thể của dự án.
        * Đánh giá tính module hóa, mức độ coupling (liên kết) và cohesion (gắn kết) của các thành phần.
        * Đề xuất các refactoring ở mức độ kiến trúc để cải thiện khả năng bảo trì, mở rộng, và kiểm thử.
        * Kiểm tra sự tuân thủ các quy tắc kiến trúc đã được người dùng định nghĩa cho dự án.
    * **Kỹ thuật:** Truy vấn CKG để hiểu cấu trúc và mối quan hệ. LLM được cung cấp kiến thức về các nguyên lý và pattern, sau đó áp dụng vào `DynamicProjectContext`.

3.  **`SecuritySentinelAI`:**
    * **Nhiệm vụ:** Phát hiện các lỗ hổng bảo mật chuyên sâu, vượt ra ngoài khả năng của các tool SAST truyền thống.
        * Phân tích luồng dữ liệu nhạy cảm (dựa trên CKG) để tìm các điểm rò rỉ hoặc xử lý không an toàn.
        * Phát hiện các lỗ hổng logic trong việc kiểm soát truy cập, xác thực, ủy quyền.
        * Cố gắng xác định các mẫu tấn công mới hoặc các biến thể của các lỗ hổng đã biết (OWASP Top 10+) dựa trên ngữ cảnh code.
        * Sàng lọc và xác minh lại các phát hiện từ tool SAST, giảm false positives bằng cách hiểu ngữ cảnh.
    * **Kỹ thuật:** Kết hợp output từ SAST tool, phân tích CKG, và LLM có khả năng suy luận về an ninh mạng.

4.  **`PerformanceProfilerAI` (Nâng cấp từ `OptiTuneAI`):**
    * **Nhiệm vụ:** Phát hiện các điểm nghẽn hiệu năng tiềm ẩn trong code, các thuật toán không hiệu quả, việc sử dụng tài nguyên lãng phí, hoặc các pattern có thể dẫn đến vấn đề về performance dưới tải nặng.
    * **Kỹ thuật:** Phân tích cấu trúc code (ví dụ: vòng lặp lồng nhau phức tạp xử lý dữ liệu lớn), truy vấn CKG để hiểu các đường dẫn thực thi thường xuyên hoặc tốn kém. LLM được cung cấp kiến thức về các anti-pattern hiệu năng. (Lưu ý: Phân tích hiệu năng tĩnh rất khó, agent này sẽ tập trung vào các *nguy cơ* tiềm ẩn hơn là đo đạc chính xác).

5.  **`StyleGuardianAgent` (Vai trò Giảm nhẹ/Tùy chọn):**
    * **Nhiệm vụ:** Đảm bảo code tuân thủ các quy ước về style cơ bản để dễ đọc và nhất quán, giúp các agent khác phân tích hiệu quả hơn. Không tập trung vào các lỗi style vụn vặt nếu đã có linter mạnh.
    * **Kỹ thuật:** Có thể chạy linter truyền thống và dùng LLM để giải thích hoặc nhóm các lỗi style quan trọng.

**VII. Công nghệ Đề xuất**

* **Frontend:** React / Vue.js / Angular (sử dụng TypeScript).
* **Backend API Gateway & Microservices:** Python (FastAPI, Flask/Django), Node.js (NestJS, Express), hoặc Golang. Python được ưu tiên cho các service liên quan đến AI/ML.
* **LLM Orchestration:** Langchain / LangGraph (Python).
* **LLM Runtime:** Ollama (cho các model local), hoặc tích hợp với các API LLM (Gemini, OpenAI).
* **Relational Database:** PostgreSQL.
* **Graph Database (cho CKG):** Neo4j (khuyến nghị cao).
* **Vector Database (cho Semantic Embeddings):** ChromaDB, Weaviate, FAISS (tích hợp).
* **Message Queue:** RabbitMQ / Kafka.
* **AST Parsing:** `tree-sitter`.
* **Containerization & Orchestration:** Docker, Kubernetes.

**VIII. Quy trình Làm việc Tổng quan của Người dùng**

1.  **Đăng ký/Đăng nhập** vào Nền tảng NovaGuard-AI.
2.  **Kết nối Tài khoản GitHub** (OAuth).
3.  **Thêm một Dự án Mới:** Chọn repository từ danh sách, chọn nhánh chính.
    * *NovaGuard-AI thực hiện "Scan Toàn bộ Dự án" lần đầu để xây dựng CKG nền tảng.*
4.  **Xem Dashboard Dự án:** Theo dõi "sức khỏe" code, các vấn đề nổi bật.
5.  **Cấu hình Dự án:** Tùy chỉnh các agent, quy tắc, model LLM cho phù hợp.
6.  **Khi Lập trình viên tạo/cập nhật Pull Request trên GitHub:**
    * NovaGuard-AI tự động nhận diện (qua webhook).
    * Thực hiện "Review PR Tự động".
    * Đăng comment tóm tắt lên PR GitHub với link tới báo cáo chi tiết trên NovaGuard-AI.
7.  **Xem Báo cáo Review Chi tiết** trên NovaGuard-AI, thảo luận, cung cấp feedback.
8.  **Khắc phục code và push commit mới lên PR.**
    * *NovaGuard-AI có thể tự động re-scan PR (nếu được cấu hình).*
9.  **Định kỳ hoặc theo yêu cầu, thực hiện "Scan Toàn bộ Dự án"** để kiểm tra nợ kỹ thuật và các vấn đề kiến trúc tổng thể.

**IX. Mô hình Triển khai (Gợi ý)**

* **Giai đoạn đầu:** Có thể tập trung vào mô hình **SaaS** để người dùng dễ dàng tiếp cận và sử dụng. Cần chiến lược bảo mật dữ liệu và code của khách hàng cực kỳ nghiêm ngặt.
* **Lộ trình dài hạn:** Cung cấp tùy chọn **On-Premise/Self-Hosted** cho các doanh nghiệp lớn có yêu cầu bảo mật cao hoặc muốn tích hợp sâu vào hạ tầng nội bộ.

**X. Lộ trình Phát triển Gợi ý (Các Giai đoạn Chính)**

1.  **MVP 1 (Nền tảng Cơ bản & Review PR Thông minh):**
    * Xác thực người dùng, kết nối GitHub, thêm dự án.
    * "Review PR Tự động" với 2-3 Agent chuyên sâu (ví dụ: `DeepLogicBugHunterAI`, `ArchitecturalAnalystAI` ở mức cơ bản). MCP và CKG ở mức độ đơn giản, tập trung vào ngữ cảnh trực tiếp của PR và các file liên quan.
    * Hiển thị báo cáo review chi tiết trên web.
    * Giao diện cấu hình dự án cơ bản.
    * Hạ tầng backend cốt lõi (API, Worker, DB cơ bản).

2.  **MVP 2 (Scan Toàn bộ Dự án & CKG Nền tảng):**
    * Triển khai tính năng "Scan Toàn bộ Dự án".
    * Xây dựng phiên bản đầu tiên của Code Knowledge Graph (CKG) một cách đầy đủ hơn.
    * Cải thiện Dashboard dự án với các chỉ số từ scan toàn bộ.
    * Nâng cấp các Agent để tận dụng CKG nền tảng.

3.  **Phiên bản Tiếp theo (Hoàn thiện và Mở rộng):**
    * Hoàn thiện và tối ưu hóa CKG, trực quan hóa CKG.
    * Thêm/Nâng cấp các Agent chuyên sâu.
    * Cải thiện trải nghiệm người dùng (UX/UI) dựa trên feedback.
    * Triển khai các tính năng nâng cao: Theo dõi nợ kỹ thuật, Knowledge Base riêng của dự án, gợi ý học tập.
    * Hỗ trợ thêm các nền tảng quản lý source code khác (GitLab, Bitbucket).
    * Nghiên cứu mô hình On-Premise.

**XI. Rủi ro và Thách thức Chính**

* **Độ phức tạp Kỹ thuật:** Xây dựng CKG, các agent LLM thông minh, và một nền tảng web ổn định, có khả năng mở rộng là một thách thức lớn.
* **Bảo mật Dữ liệu và Code:** Ưu tiên hàng đầu, đặc biệt với mô hình SaaS.
* **Hiệu năng và Chi phí Hạ tầng:** Phân tích sâu có thể tốn nhiều tài nguyên. Cần tối ưu hóa và cân nhắc chi phí vận hành.
* **Chất lượng của LLM và Prompt Engineering:** Chất lượng phân tích phụ thuộc rất nhiều vào khả năng của model LLM được chọn và nghệ thuật thiết kế prompt. Cần thử nghiệm và tinh chỉnh liên tục.
* **Trải nghiệm Người dùng (UX/UI):** Phải đảm bảo người dùng có thể dễ dàng hiểu và hành động dựa trên các phân tích chuyên sâu mà không cảm thấy bị quá tải thông tin.
* **Độ chính xác và Giảm False Positives:** Cần cơ chế feedback mạnh mẽ để hệ thống ngày càng "học" và trở nên chính xác hơn.

