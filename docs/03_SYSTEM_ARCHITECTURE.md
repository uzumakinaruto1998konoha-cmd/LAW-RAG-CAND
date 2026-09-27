# 03. System Architecture

## 1. Baseline đề xuất
Kiến trúc modular monolith cho API và điều phối nghiệp vụ, cộng worker ingestion riêng trong cùng codebase/deployment; giao tiếp qua PostgreSQL và hàng đợi bền vững do PostgreSQL điều phối ở baseline. PostgreSQL là nguồn dữ liệu chuẩn cho tài liệu, cấu trúc, metadata, ACL, trạng thái công việc và audit. Qdrant giữ vector có tham chiếu tới chunk/version; index có thể táu tạo. Ollama phục vụ embedding/LLM cục bộ theo lựa chọn model. React/TypeScript gọi FastAPI. Docker Compose điều phối dịch vụ.

> Ingestion jobs dùng bảng PostgreSQL `ingestion_job`; không thêm broker/framework. Worker claim/lease và recovery cần được chốt trước khi bật worker production.

## 2. Thành phần và trách nhiệm
- Web UI: đăng nhập, tra cứu/chat, quản trị tài liệu, duyệt extraction, quản lý người dùng/index/audit theo quyền.
- FastAPI: xác thực/ủy quyền, API, orchestration retrieval/RAG, kiểm tra citation, quản trị.
- API layer (PHASE 5): `src/law_rag/api/` với `create_app()` dựng app `/api/v1`, `ApiContainer` giữ service graph và là enforcement point duy nhất cho ACL/RBAC, `security.py` (bearer token) và `acl.py` (collection ACL deny-by-default nối vào `AuthorizationService.check_collection_access` mà retrieval gọi trước ranking). Endpoint và envelope lỗi theo `docs/11_API_SPECIFICATION.md` mục 6.
- Ingestion worker: nhận job, kiểm tra file, trích xuất/OCR, cấu trúc, metadata, dedup, chờ duyệt và lập index.
- Ingestion job/audit: PostgreSQL giữ trạng thái job và audit event; migration `migrations/0001_ingestion_engine.sql`; connection factory được wiring từ runtime, không ép driver vào package domain.
- PostgreSQL: hồ sơ tài liệu và phiên bản, nội dung/định vị chuẩn, cấu trúc pháp lý, quan hệ, ACL/RBAC, job, cấu hình và audit.
- Qdrant: vector theo chunk và phiên bản index; không phải nguồn duy nhất để tái dựng nội dung.
- Ollama: inference tại chỗ; model cụ thể và năng lực tiếng Việt TBD.
- File storage: persistent filesystem volume cho blob gốc/artefact; content-hash internal key, quarantine trước xử lý và atomic promote sau xác thực. PostgreSQL lưu storage key; backup gồm blob volume và PostgreSQL.
- Ingestion v1: PyMuPDF 1.28.2 (PDF), python-docx 1.2.0 (DOCX), Pillow 12.3.0 (ảnh), UTF-8 strict (text), Tesseract 5.5.3 + Vietnamese `vie` traineddata (OCR cục bộ). PyMuPDF AGPL v3 được chủ dự án chấp thuận cho triển khai nội bộ; python-docx MIT, Pillow MIT-CMU, Tesseract/model Apache-2.0. OCR mean dưới 90/100, không có text hoặc lỗi OCR dẫn tới review; không tự duyệt.

## 3. Luồng ingest
Upload → kiểm tra loại/kích thước/hash → tạo Document/DocumentVersion → job → text extraction/OCR → chuẩn hóa và page mapping → parse cấu trúc/metadata/quan hệ → dedup và cảnh báo → review/approval → chunk version → embedding → upsert Qdrant → cập nhật index manifest/trạng thái. Bước lỗi có trạng thái, retry có kiểm soát và audit.

## 4. Luồng truy vấn
UI → xác thực/RBAC → chuẩn hóa câu hỏi và bộ lọc → truy vấn PostgreSQL BM25/full-text cùng Qdrant vector theo ACL/metadata → hợp nhất/rerank → kiểm tra hiệu lực và xung đột → chọn đoạn evidence → Ollama tạo câu trả lời có cấu trúc → validator đối chiếu mọi citation với evidence → trả lời, cảnh báo, nguồn và page locator. Khi evidence không đủ, trả lời không đủ căn cứ.

## 5. Biên tin cậy và vận hành
LAN/offline là mục tiêu. Không có kết nối cloud mặc định. File upload không tin cậy; kiểm tra và cách ly trước xử lý. Quyền áp dụng ở truy vấn dữ liệu và lớp ứng dụng; không dựa riêng vào lọc UI. Secrets lấy từ cấu hình triển khai an toàn, không commit/hard-code. Backup gồm PostgreSQL, blob và cấu hình/manifest; Qdrant có thể snapshot hoặc tái lập theo chính sách TBD.

## 6. Quyết định cần khóa
Xem `17_DECISION_LOG.md`: ingestion storage/OCR/parser/job persistence được chốt cho v1; embedding/reranker/LLM, BM25 backend trong PostgreSQL, auth, phân loại ACL và mức bảo đảm offline còn mở. Không tự ý thay đổi stack đã nêu.
