
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

