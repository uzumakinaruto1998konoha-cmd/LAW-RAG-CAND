# 11. API Specification

## 1. Quy ước
REST JSON qua FastAPI; version prefix `/api/v1`; OpenAPI là contract. Authentication, pagination, error envelope, rate limits, idempotency và upload transport TBD. API luôn xác thực/ủy quyền ở server. Không đưa secrets vào query/body/log.

## 2. Nhóm endpoint dự kiến
- Auth/user/role: session, users, roles, permissions.
- Ingestion: upload, job status/retry/cancel, extraction preview, review/approve.
- Knowledge: documents, versions, metadata, legal nodes, relations, validity timeline, files/pages.
- Retrieval/chat: search, conversations, messages, evidence/citations, feedback.
- Index: manifests, build/rebuild, activate/rollback/status.
- Audit/operations: audit events, health/readiness, backup/restore administration (chỉ quyền chuyên biệt; thực thi chi tiết TBD).

## 3. Hợp đồng logic quan trọng
Chat request: `question`, `as_of_date?`, `filters?`, `conversation_id?`. Response: `answer`, `insufficient_evidence`, `as_of_date`, `citations[]`, `warnings[]`, `trace_id`. Citation fields theo `09_CITATION_SPECIFICATION.md`.

Upload response: `document_id`, `version_id`, `job_id`, `status`, `duplicate_match?`. Job status trả phase, progress, warning/error code và timestamps, không lộ stack trace.

## 4. Lỗi
Chuẩn hóa lỗi: code ổn định, message an toàn, request/trace ID, field errors khi validation. 401/403 phân biệt xác thực và quyền; 404 không làm lộ tài liệu không được phép; 409 cho trạng thái xung đột; 422 validation; 5xx chung không kèm secrets.

## 5. Yêu cầu contract
OpenAPI mô tả schema, permission, trạng thái, ngày theo ISO-8601 và phân trang. Mọi endpoint file/citation phải kiểm tra ACL. Contract chi tiết sẽ khóa trước triển khai Phase tương ứng; danh sách route hiện là thiết kế, không phải cam kết code ngay.

## 6. Contract đã hiện thực (PHASE 5, 2026-09-27)
Prefix `/api/v1`; OpenAPI ở `/api/v1/openapi.json`, Swagger UI ở `/api/v1/docs`. Mã nguồn: `src/law_rag/api/`.

| Method | Path | Quyền | Mô tả |
|---|---|---|---|
| GET | `/health` | công khai | Liveness + `architecture_version` |
| GET | `/ready` | công khai | Readiness theo subsystem (không lộ dữ liệu) |
| GET | `/me` | đã xác thực | Người dùng hiện tại + quyền server đã resolve |
| POST | `/search` | `search.query` | Hybrid search, ACL trước ranking, trả `trace_id` |
| POST | `/chat` | `chat.query` | Trả lời có căn cứ + citation do server sinh |
| POST | `/conversations` | `chat.query` | Tạo hội thoại (201) |
| GET | `/conversations` | `chat.query` | Liệt kê hội thoại của caller (hỗ trợ limit/offset) |
| GET | `/conversations/{id}` | `chat.query` | Hội thoại của chính người gọi, khác → 404 |
| GET | `/documents` | `document.view` | Danh sách tài liệu đọc được (lọc ACL, limit/offset) |
| GET | `/documents/{id}` | `document.view` | Tài liệu + chunk; ngoài quyền → 404 |
| POST | `/documents/upload` | `document.upload` | Nạp tài liệu (202), yêu cầu `Idempotency-Key` |
| GET | `/jobs/{job_id}` | `document.upload` hoặc `audit.view` | Trạng thái job; người khác → 404 |
| GET | `/jobs/{job_id}/review` | `document.edit_metadata` | Xem metadata và quan hệ chờ thẩm định |
| POST | `/jobs/{job_id}/review` | `document.edit_metadata` | Cập nhật điều chỉnh metadata/quan hệ sau thẩm định |
| POST | `/jobs/{job_id}/approve` | `document.approve` | Ký duyệt phát hành (release) văn bản vào kho tri thức |
| POST | `/jobs/{job_id}/retry` | `document.upload` | Thử lại job xử lý bị lỗi |
| GET | `/collections` | đã xác thực | Danh sách collection và cấp độ quyền của user |
| GET | `/traces/{trace_id}` | chủ trace hoặc `audit.view` | Audit truy vấn (chỉ chunk id, không trả nội dung) |

Xác thực: header `Authorization: Bearer <token>`; server chỉ giữ SHA-256 của token và map sang `AppUser`. RBAC deny-by-default theo ma trận vai trò có thể ghi đè khi triển khai. Phân trang `limit` & `offset` đã được hiện thực cho `/documents` và `/conversations`.

Upload transport tạm thời: body thô là nội dung file, `filename` ở query, `Idempotency-Key` ở header; giới hạn kích thước được kiểm tra khi đọc stream (413) trước khi ghi blob. `document_id`/`version_id` là `null` cho tới khi version được duyệt và release, nên nội dung chưa duyệt không có địa chỉ để truy cập.

Envelope lỗi chuẩn: `{"error": {"code", "message", "request_id", "field_errors": [{"field", "message", "code"}]}}` với 401 xác thực, 403 quyền, 404 không lộ sự tồn tại tài liệu ngoài quyền, 409 xung đột idempotency/trạng thái, 413 quá lớn, 415 định dạng, 422 validation, 503 chưa cấu hình, 5xx chung không kèm stack trace hay secret.

Hành vi đã kiểm chứng: FastAPI giải mã body JSON trước khi chạy dependency, nên body hỏng trả 422 kể cả khi thiếu token; phản hồi này không chứa thông tin về kho dữ liệu, người dùng hay quyền. Mọi trường hợp body hợp lệ đều phải qua xác thực và kiểm tra quyền trước khi đọc dữ liệu.
