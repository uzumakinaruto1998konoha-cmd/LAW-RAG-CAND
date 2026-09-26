# 15. Roadmap

## PHASE 0 — Specification
**Mục tiêu:** Hoàn tất và phê duyệt baseline tài liệu. **Đầu ra:** 18 spec, state, task board, decision log. **Exit:** nhất quán; TBD có owner/decision; kiến trúc và requirement baseline được chấp thuận. **Trạng thái:** tài liệu khởi tạo được lập; cần chủ dự án quyết định TBD để khóa.

## PHASE 1 — Document Ingestion Engine
Định nghĩa và xây pipeline upload, file validation, extraction/OCR, page mapping, metadata/structure parsing, dedup, versioning, review workflow và audit. **Exit:** bộ mẫu định dạng chạy được; lỗi/retry/provenance có thể kiểm tra; người duyệt xác nhận.

## PHASE 2 — Knowledge Base
Hoàn thiện schema PostgreSQL, pháp nhân pháp lý, hiệu lực/relations, ACL, document/version UI/API, quản trị dữ liệu và chunk set chuẩn. **Exit:** quản lý vòng đời/version/relations và dữ liệu được duyệt.

## PHASE 3 — Hybrid Retrieval
BM25 + vector + metadata/ACL filtering + fusion/reranking, index manifest, rebuild/rollback, benchmark. **Exit:** metrics đạt ngưỡng được duyệt, ACL leakage bằng 0.

## PHASE 4 — RAG + LLM
Ollama local, orchestration, prompt/context, warnings/conflicts, citation validator, refusal/insufficient evidence và evaluation. **Exit:** groundedness/citation/effectiveness đạt tiêu chí đã chốt.

## PHASE 5 — Web Application
React/TypeScript cho search/chat, viewer trang, kho tài liệu, ingestion review, quản trị và trạng thái lỗi. **Exit:** luồng người dùng chính hoàn chỉnh, accessibility và API contract đạt.

## PHASE 6 — Security
RBAC hoàn thiện, hardening upload/parser, auth/session, audit, secrets, threat review, bảo vệ backup. **Exit:** security acceptance, không có đường bypass quyền nghiêm trọng.

## PHASE 7 — Testing
Regression, integration/E2E, security, retrieval/RAG evaluation, tải, offline và restore drills. **Exit:** release gates và rủi ro được ký duyệt.

## PHASE 8 — Deployment
Compose production profile, runbook, backup/restore, upgrade/rollback, vận hành LAN/offline và bàn giao. **Exit:** triển khai tái lập, khôi phục diễn tập thành công, chủ dự án nghiệm thu.

**Quy tắc:** không bắt đầu code trước khi Phase 0 được chủ dự án chấp thuận; thứ tự phụ thuộc có thể chồng lấn chỉ khi decision log cho phép.
