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
