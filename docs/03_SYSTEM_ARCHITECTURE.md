# 03. System Architecture

## 1. Baseline đề xuất
Kiến trúc modular monolith cho API và điều phối nghiệp vụ, cộng worker ingestion riêng trong cùng codebase/deployment; giao tiếp qua PostgreSQL và hàng đợi bền vững do PostgreSQL điều phối ở baseline. PostgreSQL là nguồn dữ liệu chuẩn cho tài liệu, cấu trúc, metadata, ACL, trạng thái công việc và audit. Qdrant giữ vector có tham chiếu tới chunk/version; index có thể táu tạo. Ollama phục vụ embedding/LLM cục bộ theo lựa chọn model. React/TypeScript gọi FastAPI. Docker Compose điều phối dịch vụ.

> Hàng đợi PostgreSQL là đề xuất cần chốt; không thêm broker/framework cho tới khi quyết định.

## 2. Thành phần và trách nhiệm
- Web UI: đăng nhập, tra cứu/chat, quản trị tài liệu, duyệt extraction, quản lý người dùng/index/audit theo quyền.
- FastAPI: xác thực/ủy quyền, API, orchestration retrieval/RAG, kiểm tra citation, quản trị.
- Ingestion worker: nhận job, kiểm tra file, trích xuất/OCR, cấu trúc, metadata, dedup, chờ duyệt và lập index.
- PostgreSQL: hồ sơ tài liệu và phiên bản, nội dung/định vị chuẩn, cấu trúc pháp lý, quan hệ, ACL/RBAC, job, cấu hình và audit.
- Qdrant: vector theo chunk và phiên bản index; không phải nguồn duy nhất để tái dựng nội dung.
- Ollama: inference tại chỗ; model cụ thể và năng lực tiếng Việt TBD.
- File storage: lưu blob gốc/artefact. Loại lưu trữ (filesystem volume hay object-compatible tự host) TBD; không coi là thêm dịch vụ đã chốt.

## 3. Luồng ingest
Upload → kiểm tra loại/kích thước/hash → tạo Document/DocumentVersion → job → text extraction/OCR → chuẩn hóa và page mapping → parse cấu trúc/metadata/quan hệ → dedup và cảnh báo → review/approval → chunk version → embedding → upsert Qdrant → cập nhật index manifest/trạng thái. Bước lỗi có trạng thái, retry có kiểm soát và audit.

## 4. Luồng truy vấn
UI → xác thực/RBAC → chuẩn hóa câu hỏi và bộ lọc → truy vấn PostgreSQL BM25/full-text cùng Qdrant vector theo ACL/metadata → hợp nhất/rerank → kiểm tra hiệu lực và xung đột → chọn đoạn evidence → Ollama tạo câu trả lời có cấu trúc → validator đối chiếu mọi citation với evidence → trả lời, cảnh báo, nguồn và page locator. Khi evidence không đủ, trả lời không đủ căn cứ.

## 5. Biên tin cậy và vận hành
LAN/offline là mục tiêu. Không có kết nối cloud mặc định. File upload không tin cậy; kiểm tra và cách ly trước xử lý. Quyền áp dụng ở truy vấn dữ liệu và lớp ứng dụng; không dựa riêng vào lọc UI. Secrets lấy từ cấu hình triển khai an toàn, không commit/hard-code. Backup gồm PostgreSQL, blob và cấu hình/manifest; Qdrant có thể snapshot hoặc tái lập theo chính sách TBD.

## 6. Quyết định cần khóa
Xem `17_DECISION_LOG.md`: lưu blob, OCR/parser, embedding/reranker/LLM, BM25 backend trong PostgreSQL, auth, hàng đợi, phân loại ACL và mức bảo đảm offline. Không tự ý thay đổi stack đã nêu.
