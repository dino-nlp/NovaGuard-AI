# NovaGuard AI: Người Đồng Hành Review Code Thông Minh

[![Shield Icon][shield-icon]][shield-icon] **NovaGuard AI là một GitHub Action review code thông minh, sử dụng hệ thống Đa Agent Lai (Hybrid Multi-Agent System) kết hợp các công cụ phân tích tĩnh truyền thống với các mô hình ngôn ngữ lớn (LLM) chạy local qua Ollama, giúp nâng cao chất lượng và bảo mật mã nguồn của bạn.**

---

## Mục lục

- [NovaGuard AI: Người Đồng Hành Review Code Thông Minh](#novaguard-ai-người-đồng-hành-review-code-thông-minh)
  - [Mục lục](#mục-lục)
  - [Tổng quan](#tổng-quan)
  - [Tính năng nổi bật](#tính-năng-nổi-bật)
  - [Cách hoạt động](#cách-hoạt-động)
  - [Bắt đầu](#bắt-đầu)
    - [Yêu cầu tiên quyết (Cho Self-Hosted Runner)](#yêu-cầu-tiên-quyết-cho-self-hosted-runner)
    - [Sử dụng NovaGuard AI trong Workflow của bạn](#sử-dụng-novaguard-ai-trong-workflow-của-bạn)
  - [Cấu hình Action](#cấu-hình-action)
  - [Xem kết quả Review](#xem-kết-quả-review)
  - [Đóng góp](#đóng-góp)
  - [Giấy phép](#giấy-phép)
  - [Lộ trình phát triển (Tương lai)](#lộ-trình-phát-triển-tương-lai)

---

## Tổng quan

NovaGuard AI được thiết kế để trở thành một "người đồng hành" review code tự động, thông minh và bảo mật cho các dự án trên GitHub. Bằng cách phân tích code trong Pull Request (PR), NovaGuard AI cung cấp các nhận xét, cảnh báo về lỗi tiềm ẩn, vấn đề bảo mật, vi phạm phong cách code và gợi ý cải thiện code.

**Tại sao chọn NovaGuard AI?**

* **Review Toàn Diện:** Phân tích đa khía cạnh từ lỗi cú pháp, logic, bảo mật đến tối ưu hóa.
* **Bảo Mật Dữ Liệu:** Toàn bộ quá trình phân tích (bao gồm cả LLM) chạy trên self-hosted runner của bạn, đảm bảo code không bao giờ rời khỏi hạ tầng của bạn.
* **Tăng Tốc Độ Phát Triển:** Giảm thời gian review thủ công, giúp đội ngũ tập trung vào các tác vụ quan trọng hơn.
* **Nâng Cao Chất Lượng Code:** Phát hiện sớm các vấn đề, giúp code sạch hơn, an toàn hơn và dễ bảo trì hơn.
* **Tùy Biến Cao:** Dễ dàng cấu hình các agent, model LLM và quy tắc phân tích cho từng dự án.

## Tính năng nổi bật

* **Hệ thống Đa Agent Lai:** Kết hợp sức mạnh của các công cụ phân tích tĩnh (linters, SAST) và nhiều agent LLM chuyên biệt (StyleGuardian, BugHunter, SecuriSense, OptiTune, MetaReviewer).
* **Xử lý LLM Local với Ollama:** Tận dụng các model ngôn ngữ lớn mã nguồn mở chạy trên hạ tầng của bạn thông qua [Ollama](https://ollama.com/), đảm bảo tính riêng tư và kiểm soát.
* **Tích hợp GitHub Action:** Dễ dàng tích hợp vào quy trình CI/CD hiện có của bạn.
* **Định dạng Output SARIF:** Xuất kết quả dưới dạng SARIF (Static Analysis Results Interchange Format), tương thích với tính năng Code Scanning của GitHub.
* **Cấu hình Linh hoạt:** Cho phép tùy chỉnh model LLM, câu lệnh tool, và prompt cho từng agent.
* **Hỗ trợ nhiều Ngôn ngữ:** Được thiết kế để có thể mở rộng cho nhiều ngôn ngữ lập trình (hiện tại tập trung vào Python và các ngôn ngữ phổ biến khác được hỗ trợ bởi tool và LLM).

## Cách hoạt động

Khi một Pull Request được tạo hoặc cập nhật, NovaGuard AI sẽ:

1.  **Trigger Workflow:** GitHub Action được kích hoạt.
2.  **Checkout Code:** Lấy mã nguồn của PR và mã nguồn của NovaGuard AI action về self-hosted runner.
3.  **Phân tích Thay đổi:** Xác định các file đã thay đổi trong PR.
4.  **Chạy Phân tích Tĩnh (Tier 1):** Thực thi các công cụ linter (ví dụ: Pylint) và SAST cơ bản (ví dụ: Semgrep) trên các file thay đổi để phát hiện các vấn đề cơ bản.
5.  **Kích hoạt Agent LLM:**
    * `SharedReviewContext` (chứa thông tin PR, code thay đổi, kết quả tool Tier 1, cấu hình) được chuẩn bị.
    * Một graph (sử dụng LangGraph) điều phối việc kích hoạt các agent LLM chuyên biệt:
        * **StyleGuardianAgent:** Phân tích phong cách code, convention, dựa trên output linter và LLM.
        * **BugHunterAgent:** Tìm kiếm lỗi logic, null pointers, resource leaks bằng LLM.
        * **SecuriSenseAgent:** Phân tích lỗ hổng bảo mật, đánh giá output SAST bằng LLM.
        * **OptiTuneAgent:** Gợi ý tối ưu hóa hiệu năng, sử dụng các tính năng ngôn ngữ mới bằng LLM.
        * **(Tùy chọn) MetaReviewerAgent:** Tổng hợp, lọc trùng lặp, và đánh giá độ tin cậy của các finding từ các agent khác.
6.  **Tạo Báo cáo SARIF:** Tất cả các finding từ tool Tier 1 và các agent LLM được tổng hợp và chuyển đổi thành một báo cáo định dạng SARIF.
7.  **Upload và Hiển thị:** File SARIF được upload lên GitHub, kết quả sẽ được hiển thị trong tab "Security" -> "Code scanning alerts" của repository và trực tiếp trên các dòng code thay đổi trong PR.

## Bắt đầu

### Yêu cầu tiên quyết (Cho Self-Hosted Runner)

Để NovaGuard AI hoạt động, self-hosted runner của bạn cần được cài đặt và cấu hình các thành phần sau:

1.  **GitHub Self-Hosted Runner:**
    * Làm theo hướng dẫn chính thức của GitHub để [thêm self-hosted runner](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/adding-self-hosted-runners) vào repository hoặc organization của bạn.
    * Đảm bảo runner có label `self-hosted` (hoặc label bạn chỉ định trong workflow).

2.  **Docker:**
    * Docker phải được cài đặt trên máy chạy self-hosted runner.
    * User chạy tiến trình runner (ví dụ: `dino`) phải có quyền thực thi lệnh `docker` (thường là thêm user vào group `docker`).

3.  **Ollama:**
    * Cài đặt Ollama trên máy chạy self-hosted runner theo [hướng dẫn từ trang chủ Ollama](https://ollama.com/download).
    * **Quan trọng:** Sau khi cài đặt, bạn cần cấu hình Ollama để chấp nhận kết nối từ Docker container. Ollama mặc định có thể chỉ lắng nghe trên `127.0.0.1`. Bạn cần nó lắng nghe trên `0.0.0.0` hoặc một địa chỉ IP mà Docker container có thể truy cập.
        * Nếu Ollama chạy như một systemd service (phổ biến sau khi cài bằng script `curl ... | sh`), bạn cần sửa file service của Ollama (thường ở `/etc/systemd/system/ollama.service`). Thêm hoặc chỉnh sửa dòng `Environment` trong section `[Service]` để bao gồm `OLLAMA_HOST=0.0.0.0` (hoặc `OLLAMA_HOST=0.0.0.0:11434`).
            ```ini
            [Service]
            Environment="OLLAMA_HOST=0.0.0.0"
            # ... các dòng khác ...
            ```
        * Sau đó, reload systemd daemon và restart Ollama service:
            ```bash
            sudo systemctl daemon-reload
            sudo systemctl restart ollama
            ```
        * Kiểm tra lại bằng `netstat -tulnp | grep 11434` để đảm bảo Ollama đang lắng nghe trên `:::11434` hoặc `0.0.0.0:11434`.

4.  **Pull các Model LLM cần thiết:**
    * NovaGuard AI sử dụng các model LLM được định nghĩa trong file `config/models.yml`. Dựa trên `active_mode` (mặc định là `production` hoặc có thể là `test` nếu bạn set biến môi trường `NOVAGUARD_ACTIVE_MODE`), bạn cần pull các model tương ứng về Ollama server trên máy runner.
    * Ví dụ, để pull các model cho `test` mode (thường nhỏ và nhanh hơn):
        ```bash
        ollama pull tinydolphin:1.1b-v2.8-q4_K_M
        ollama pull phi:2.7b-chat-v2-q4_K_M  # Hoặc model phi-3 nếu bạn đã cập nhật config
        ollama pull orca-mini:7b-v3-q4_K_M
        # Pull thêm các model khác nếu bạn cấu hình trong models.yml
        ```
    * Để pull model cho `production` mode (ví dụ, dựa trên gợi ý trước đó):
        ```bash
        ollama pull llama3:8b-instruct 
        ollama pull deepseek-coder-v2:33b-instruct # Đây là model lớn, cần VRAM
        ollama pull codellama:34b-instruct 
        ollama pull codegemma:7b-instruct
        ollama pull mistral:7b-instruct # Hoặc phiên bản mới hơn
        # Pull các model bạn đã chọn cho production mode
        ```
    * Kiểm tra các model đã có bằng `ollama list`.

5.  **Firewall:** Đảm bảo firewall trên máy runner cho phép kết nối đến cổng `11434` (hoặc cổng Ollama bạn cấu hình) từ mạng nội bộ của Docker (thường là `172.17.0.0/16` nếu dùng bridge network mặc định).

### Sử dụng NovaGuard AI trong Workflow của bạn

1.  Trong repository bạn muốn review code, tạo file workflow (ví dụ: `.github/workflows/code_review.yml`) với nội dung sau:

    ```yaml
    name: NovaGuard AI Code Review

    on:
      pull_request:
        branches: [ main, master ] # Trigger khi có PR vào nhánh main hoặc master

    permissions:
      contents: read         # Cần để checkout code
      # pull-requests: write # Bỏ comment nếu bạn thêm tính năng comment trực tiếp vào PR
      security-events: write # Cần để upload SARIF report

    jobs:
      novaguard_review:
        name: Run NovaGuard AI Review
        runs-on: self-hosted # Chỉ định chạy trên self-hosted runner của bạn

        steps:
          # 1. Checkout code của project đang được review
          - name: Checkout Project Repository
            uses: actions/checkout@v4
            with:
              fetch-depth: 0 # Lấy toàn bộ history để git diff hoạt động đúng
              clean: false   # Khuyến nghị để tránh lỗi permission khi runner dọn dẹp file cũ

          # 2. Checkout code của NovaGuard AI Action vào một thư mục con
          #    Thay 'YOUR_GITHUB_USERNAME/novaguard-ai' bằng repository chứa code NovaGuard AI của bạn
          - name: Checkout NovaGuard AI Action Code
            uses: actions/checkout@v4
            with:
              repository: dino-nlp/NovaGuard-AI # <<< THAY THẾ CHO ĐÚNG
              path: ./.novaguard-ai-action # Checkout vào thư mục này trong workspace
              # token: ${{ secrets.YOUR_PAT_IF_PRIVATE_ACTION_REPO }} # Cần nếu repo NovaGuard AI là private

          # 3. Chạy NovaGuard AI Action
          - name: Run NovaGuard AI
            uses: ./.novaguard-ai-action # Trỏ đến thư mục chứa action.yml của NovaGuard AI
            id: novaguard
            with:
              github_token: ${{ secrets.GITHUB_TOKEN }}
              # Địa chỉ Ollama server từ góc nhìn của self-hosted runner
              # Nếu Ollama chạy trên cùng máy runner và lắng nghe trên tất cả IP:
              ollama_base_url: '[http://172.17.0.1:11434](http://172.17.0.1:11434)' # Hoặc IP gateway Docker bridge của bạn
              # Hoặc nếu dùng Docker Desktop (Mac/Windows) cho runner:
              # ollama_base_url: '[http://host.docker.internal:11434](http://host.docker.internal:11434)' 
              
              # Tùy chọn: Đường dẫn đến thư mục config NovaGuard AI riêng của project này
              # project_config_path: '.github/novaguard_config' 
              
              sarif_output_file: 'results/novaguard-review.sarif' # Tên file SARIF output
              
              # Tùy chọn: Mức độ nghiêm trọng tối thiểu để làm action fail
              # fail_on_severity: 'warning' # 'error', 'warning', 'note', 'none'
            # env:
              # NOVAGUARD_ACTIVE_MODE: "test" # Bỏ comment để ép chạy test mode models

          # 4. Upload SARIF Report lên GitHub Code Scanning
          - name: Upload SARIF to GitHub Code Scanning
            if: success() || failure() # Luôn upload report, ngay cả khi bước trước fail
            uses: github/codeql-action/upload-sarif@v3
            with:
              sarif_file: ${{ steps.novaguard.outputs.sarif_file_path }}
              category: 'NovaGuardAI-${{ github.head_ref }}' # Phân loại kết quả theo nhánh
    ```

2.  **Giải thích các Input:**
    * `github_token`: (Bắt buộc) Token mặc định của GitHub, cần cho các tương tác API cơ bản.
    * `ollama_base_url`: (Bắt buộc) URL đầy đủ của Ollama server đang chạy trên self-hosted runner của bạn (ví dụ: `http://172.17.0.1:11434` hoặc `http://localhost:11434` nếu Ollama và runner trên cùng máy và Ollama lắng nghe trên localhost từ góc nhìn runner).
    * `project_config_path`: (Tùy chọn) Đường dẫn tương đối (trong repository được review) đến thư mục chứa cấu hình NovaGuard AI riêng cho project đó (ghi đè cấu hình mặc định của action). Ví dụ: `.github/novaguard_config/`.
    * `sarif_output_file`: (Tùy chọn) Tên file (và đường dẫn tương đối trong workspace) để lưu báo cáo SARIF. Mặc định: `novaguard-report.sarif`.
    * `fail_on_severity`: (Tùy chọn) Mức độ nghiêm trọng tối thiểu (`error`, `warning`, `note`) của một finding để khiến Action bị đánh dấu là thất bại. Mặc định `none` (không bao giờ fail dựa trên severity).

## Cấu hình Action

* **Inputs Cơ bản:** Các input được mô tả ở trên có thể được cấu hình trực tiếp trong file workflow.
* **Cấu hình Nâng cao (Nếu bạn fork/clone NovaGuard AI):**
    * **Models (`config/models.yml`):** Định nghĩa các model LLM được sử dụng cho từng agent và cho các "mode" khác nhau (ví dụ: `production`, `test`). Bạn có thể thay đổi tên model, thêm model mới.
    * **Tools (`config/tools.yml`):** Cấu hình dòng lệnh để chạy các công cụ phân tích tĩnh bên ngoài như Pylint, Semgrep.
    * **Prompts (`config/prompts/`):** Chứa các file template (Markdown) cho prompt của từng agent. Bạn có thể tinh chỉnh các prompt này để cải thiện chất lượng review.
* **Cấu hình theo Project (`project_config_path`):**
    Nếu bạn cung cấp `project_config_path`, NovaGuard AI sẽ tìm các file `models.yml`, `tools.yml`, và thư mục `prompts/` trong đường dẫn đó của repository đang được review. Các cấu hình này sẽ được merge và ghi đè lên cấu hình mặc định của action, cho phép bạn tùy biến NovaGuard AI cho từng project cụ thể.

## Xem kết quả Review

Sau khi workflow chạy xong:

1.  **Trong Pull Request:**
    * Truy cập tab "Files changed".
    * Các finding từ NovaGuard AI (nếu có) sẽ được hiển thị dưới dạng chú thích (annotations) trực tiếp trên các dòng code liên quan.
2.  **Trong Tab "Security":**
    * Truy cập tab "Security" của repository, sau đó chọn "Code scanning alerts".
    * Bạn sẽ thấy danh sách tất cả các cảnh báo được phát hiện bởi NovaGuard AI, được phân loại theo `category` bạn đã đặt trong bước upload SARIF.
    * Bạn có thể xem chi tiết từng cảnh báo, lịch sử, và quản lý chúng (ví dụ: dismiss false positive).

## Đóng góp

(Phần này bạn có thể tự điền nếu muốn người khác đóng góp vào dự án NovaGuard AI của bạn)
Ví dụ:
Chúng tôi rất hoan nghênh sự đóng góp từ cộng đồng! Vui lòng xem qua `CONTRIBUTING.md` (nếu có) để biết thêm chi tiết về cách báo lỗi, đề xuất tính năng, hoặc gửi Pull Request.

**Phát triển Local:**
* Script `run_local.sh` được cung cấp để kiểm thử action trên máy local của bạn trước khi commit. Tham khảo nội dung script để biết cách cấu hình và chạy.
* Chạy unit tests:
    ```bash
    python -m unittest discover tests
    ```

## Giấy phép

(Phần này bạn cần quyết định và chọn một giấy phép phù hợp cho dự án của mình, ví dụ: MIT, Apache 2.0)
Ví dụ:
Dự án này được cấp phép dưới Giấy phép MIT. Xem file `LICENSE` để biết chi tiết.

## Lộ trình phát triển (Tương lai)

* Tinh chỉnh và cải thiện độ chính xác của các agent LLM.
* Thêm khả năng comment tóm tắt trực tiếp vào Pull Request.
* Hỗ trợ auto-fix cho một số loại lỗi đơn giản (có giám sát).
* Mở rộng hỗ trợ cho nhiều ngôn ngữ lập trình hơn.
* Tối ưu hóa hiệu năng và thời gian chạy của action.
* Thêm nhiều agent chuyên biệt hơn (ví dụ: kiểm tra tài liệu, độ bao phủ test).

---

[shield-icon]: https://img.shields.io/badge/NovaGuard_AI-Review_Co--Pilot-blue?style=for-the-badge&logo=githubactions