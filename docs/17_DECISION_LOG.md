# 17. Decision Log

Quyết định được đánh dấu **Proposed** chưa phải phê duyệt. Chủ dự án là decision owner mặc định; ngày cụ thể được ghi khi chốt.

| ID | Chủ đề | Baseline/đề xuất | Trạng thái | Cần quyết định |
|---|---|---|---|---|
| ADR-001 | Stack | Python/FastAPI, React/TS, PostgreSQL, Qdrant, Ollama, Docker Compose | Accepted (user requirement) | Không đổi nếu chưa có yêu cầu mới |
| ADR-002 | Kiến trúc dịch vụ | Modular monolith + worker riêng | Proposed | Chấp thuận topology và cách deploy worker |
| ADR-003 | Job queue | Bảng `ingestion_job` trong PostgreSQL; worker claim/update theo trạng thái; dùng driver DB-API tương thích được wiring từ deployment, không thêm broker | Accepted (2026-09-26) | Chọn phiên bản driver ở deployment; xử lý claim/lease và concurrency benchmark trước production scale |
| ADR-004 | File storage | Persistent filesystem volume; hash-derived internal key, quarantine rồi atomic promote; backup cùng PostgreSQL | Accepted (ingestion v1) | Xem lại nếu triển khai object-compatible storage |
| ADR-005 | OCR/extraction | PyMuPDF 1.28.2 (AGPL v3), python-docx 1.2.0 (MIT), Pillow 12.3.0 (MIT-CMU); Tesseract 5.5.3 + `vie` model (Apache-2.0); OCR mean <90/100 đưa review | Accepted (2026-09-26; project owner approved PyMuPDF AGPL for internal deployment) | External redistribution needs renewed license review; runtime records traineddata SHA-256; validate quality with approved corpus |
| ADR-006 | Parser pháp luật | Rule-based parser + manual review; pipeline ID `ingestion-v1` và `legal-parse-v1`; corpus manifest theo docs/05 và docs/13 | Accepted (ingestion v1 design, legal parsing 2026-09-27) | Mở rộng tự động hóa chỉ sau đánh giá corpus được duyệt |
| ADR-007 | Embedding/LLM/reranker | Chạy qua Ollama/local model | Open | Model/version, license, RAM/VRAM, tiếng Việt, context |
| ADR-008 | BM25 | Lexical/full-text trong PostgreSQL là phương án đầu | Open | Có chấp nhận built-in lexical hay backend khác trong stack hiện tại |
| ADR-009 | Authentication | Local account là baseline tối thiểu | Proposed (API baseline 2026-09-27) | MFA/SSO/IdP, password policy/session |
| ADR-010 | ACL | RBAC bắt buộc; ACL theo collection/document nếu cần | Proposed (API baseline 2026-09-27) | Phân loại dữ liệu, nhóm người dùng, deny-by-default |
| ADR-011 | Hiệu lực | As-of temporal state; chỉ relation đã xác minh tác động | Proposed | Quy tắc partial amendment/repeal, nguồn xác thực |
| ADR-012 | Vận hành offline | Runtime không cloud; cập nhật qua gói cục bộ | Accepted (user requirement) | Mức air-gap và quy trình chuyển gói |
| ADR-013 | Backup/restore | PostgreSQL + blobs là nguồn khôi phục; vector rebuildable | Proposed | RPO/RTO, retention, encryption, nơi lưu, lịch |
| ADR-014 | Hiệu năng/SLA | Chưa đặt ngưỡng | Open | Users đồng thời, corpus size, latency/availability |
| ADR-015 | Data governance | Chưa chốt retention/chat/audit/deletion | Open | Thời hạn lưu, quyền xóa/ẩn danh, legal hold |
| ADR-016 | Deployment host | Windows dev; host LAN production TBD | Open | OS, GPU, TLS, network segmentation |
| ADR-017 | Security policy | RBAC/audit/secret hygiene bắt buộc | Accepted (user requirement) | Role matrix, encryption/key lifecycle, audit tamper protection |
| ADR-018 | API layer | FastAPI `/api/v1`, bearer token opaque (chỉ giữ SHA-256), RBAC deny-by-default + ACL theo collection, upload bằng body thô + `Idempotency-Key` | Proposed (2026-09-27) | Chốt role matrix cuối, phân trang, rate limit, MFA/SSO, transport upload chính thức |
| ADR-019 | Web app layer | React 18 + TypeScript + Vite 6 + Tailwind 3 + TanStack Query 5 + axios trong `frontend/`; UI chỉ trình bày, server quyết định quyền; Vitest + React Testing Library cho test UI | Proposed (2026-09-29) | Chính sách session/token phía trình duyệt (ADR-009), responsive mobile, i18n, dev seed cấp token |

## Quy tắc cập nhật
Mỗi quyết định mới ghi lựa chọn, bối cảnh, hệ quả, owner và ngày. Khi đổi quyết định, không xóa lịch sử; cập nhật tài liệu bị ảnh hưởng và `PROJECT_STATE.json`.

### Quyết định PHASE 1 ingestion design — 2026-09-26
- Owner: Project owner (Phase 0 approval và PHASE 1 được yêu cầu trong phiên này); người thực hiện: Codex.
- Bối cảnh: Hoàn tất task đầu tiên PHASE 1 trong Task Board, trước khi bắt đầu triển khai engine. Yêu cầu offline, không thêm dịch vụ cloud/API.
- Lựa chọn: Giới hạn/định dạng, parser cục bộ, storage, OCR threshold và corpus manifest v1 được mô tả tại `docs/05_DOCUMENT_INGESTION_SPECIFICATION.md`; kiến trúc vẫn modular monolith/worker và không thêm broker.
- Hệ quả: Task engine kế tiếp có đầu vào thiết kế cụ thể. Chưa cài package/binary. Trước khi đưa dependency vào repo phải xác nhận license/phân phối, pin phiên bản cụ thể và kiểm tra trên corpus có quyền sử dụng.

### Quyết định PHASE 1 job persistence — 2026-09-26
- Owner: Project owner đã phê duyệt Phase 0/Phase 1; người thực hiện: Codex.
- Bối cảnh: Task ingestion engine cần job state bền vững và audit theo kiến trúc nguồn dữ liệu chuẩn PostgreSQL; ADR-003 chưa chọn framework.
- Lựa chọn: Dùng bảng PostgreSQL `ingestion_job` và `audit_event` qua connection factory DB-API tương thích psycopg; không thêm broker/framework/driver dependency. Migration ở `migrations/0001_ingestion_engine.sql`.
- Hệ quả: Không phát sinh dependency cài mới; deployment cần wiring một driver PostgreSQL đã được duyệt. Claim/lease/recovery worker sẽ được xác định trước khi chạy production worker.

### Quyết định PHASE 1 extraction dependencies — 2026-09-26
- Owner: Project owner (đã trả lời chấp thuận PyMuPDF AGPL v3 cho triển khai nội bộ); người thực hiện: Codex.
- Bối cảnh: Task Extraction phụ thuộc parser/OCR cục bộ của ADR-005; repository cần phiên bản tái lập và runtime offline.
- Lựa chọn: Pin PyMuPDF 1.28.2, python-docx 1.2.0, Pillow 12.3.0 trong `requirements.txt`; yêu cầu Tesseract 5.5.3 và model `vie` từ `tessdata_best`, ghi SHA-256 của traineddata khi chạy. License được đối chiếu từ tài liệu/repository chính thức: PyMuPDF AGPL v3 (được duyệt nội bộ), python-docx MIT, Pillow MIT-CMU, Tesseract và `tessdata_best` Apache-2.0.
- Hệ quả: Không gọi cloud; deployment phải mang các gói/binary/model đã pin. Máy hiện tại chưa có Tesseract binary, nên OCR thật được kiểm thử bằng adapter giả và mã xử lý thiếu engine; cần corpus được cấp quyền để benchmark OCR trước khi nghiệm thu toàn Phase 1.

### Quyết định PHASE 1 legal parsing — 2026-09-27
- Owner: Project owner (tiếp tục chuỗi task PHASE 1 đã được yêu cầu trong phiên này); người thực hiện: Codex.
- Bối cảnh: Cần metadata, cây cấu trúc và ứng viên quan hệ có provenance/confidence cùng workflow review; schema pháp lý ở docs/06 mới ở mức đề xuất và chưa có quyết định nào về parser ngoài ADR-006.
- Lựa chọn: Rule-based parser cấu hình được (`LegalParseConfig`), pipeline ID `legal-parse-v1`, lưu `parser_config_hash` cùng mỗi parse run; cây node CHAPTER/SECTION/ARTICLE/CLAUSE/POINT/APPENDIX; metadata assertion và relation candidate đều `unverified` cho tới khi reviewer quyết định; duyệt chỉ khi không còn item pending và mọi warning được acknowledge. Bảng `legal_parse_run`, `legal_node`, `metadata_assertion`, `document_relation_candidate`, `review_decision`, `document_approval` trong `migrations/0002_legal_parsing.sql`; adapter dùng connection factory DB-API sẵn có (ADR-003).
- Hệ quả: Không thêm dependency và không nhúng nội dung luật vào source; từ khóa cấu trúc/từ vựng loại văn bản nằm trong cấu hình có thể mở rộng sau khi được corpus duyệt xác nhận. Quan hệ chưa xác minh không được dùng cho hiệu lực (giữ đúng ADR-011); việc ánh xạ `Document`/`DocumentVersion` thật sang schema PHASE 2 vẫn TBD, `job_id` hiện là khóa nhận diện parse run.

### Quyết định PHASE 5 API layer — 2026-09-27
- Owner: Project owner (yêu cầu triển khai API backend REST v1 trong phiên này); người thực hiện: Codex.
- Bối cảnh: Cần lớp API để UI Phase 5 và kiểm thử tích hợp dùng được, đồng thời bổ sung xác thực/ủy quyền server-side cho ADR-009/ADR-010 vốn còn Open. ADR-001 đã chấp thuận FastAPI nên không thay đổi stack.
- Lựa chọn: FastAPI 0.141.1 + uvicorn 0.54.0 (pin trong `requirements.txt`); prefix `/api/v1`, OpenAPI là contract. Xác thực bằng bearer token opaque, registry chỉ giữ SHA-256 token và map sang `AppUser`; RBAC deny-by-default theo ma trận 5 vai trò có thể ghi đè khi triển khai; ACL collection deny-by-default được nối thẳng vào `AuthorizationService.check_collection_access` mà retrieval gọi trước ranking. Tài liệu/hội thoại/job ngoài quyền trả 404 thay vì 403 để không lộ sự tồn tại. Upload dùng body thô + `filename` query + `Idempotency-Key`, kiểm tra giới hạn kích thước ngay khi đọc stream; thêm adapter in-memory (`ingestion/memory.py`) cho dev/test, production vẫn dùng PostgreSQL (ADR-003).
- Hệ quả: 189 unit/integration test đạt, gồm 46 test API; không gọi cloud, không nhúng nội dung luật, không hard-code secret. Endpoint đang dùng store in-memory nên cần wiring PostgreSQL/Qdrant/Ollama ở PHASE 6-8; phân trang, rate limit, MFA/SSO và transport upload chính thức vẫn TBD.

### Quyết định PHASE 5 Web app layer — 2026-09-29
- Owner: Project owner (yêu cầu hoàn thiện Web UI Phase 5 trong phiên này); người thực hiện: Codex.
- Bối cảnh: `frontend/` đã có khung (router, auth, api hooks, SearchPage) nhưng thiếu 7 màn hình và không build được (`tsc -b` lỗi import, thiếu CSS entry, react-query v5 bỏ `onError` của query, `AuthProvider` chưa được gắn trong `main.tsx`). Cần hoàn thiện UI trên đúng contract `/api/v1` (ADR-018) mà không đổi backend.
- Lựa chọn: Giữ stack đã khai báo trong `package.json` (ADR-001): React 18.3, TypeScript 5.9, Vite 6, Tailwind 3, TanStack Query 5, axios, react-router 6; thêm CSS entry `src/index.css` với `@tailwind` để style có hiệu lực; tách `authContext.ts`/`AuthProvider.tsx` và `toastContext.ts` để tuân thủ react-refresh rule; dựng đủ 8 màn hình (search, chat, conversations, documents list/detail, trace, admin, health) với đầy đủ trạng thái loading/empty/error/permission-denied/insufficient-evidence/degraded; nhãn trạng thái (validity, citation, job) map ở UI nhưng mã lạ được hiển thị nguyên văn và danh mục lọc lấy từ dữ liệu server để tránh nguồn sự thật song song; không hard-code token trong UI (trang đăng nhập chỉ hướng dẫn lấy token từ deployment/test harness, đúng AGENTS §5 và docs/10). Thêm test tooling cục bộ Vitest 5 + React Testing Library 16 + jsdom (không phải dependency cloud/API) cùng `vitest.config.ts` và `npm test`.
- Vị trí quyền: UI ẩn/khóa chức năng theo `permissions` từ `/me`, nhưng server vẫn là nơi quyết định cuối cùng (docs/12 §5); mọi màn hình đọc đều gọi endpoint đã lọc ACL và hiển thị 404 là “không tồn tại hoặc ngoài quyền”.
- Hệ quả: `npm run build` (tsc -b + vite build), `npm run lint` (0 lỗi) và `npm test` (36 test/9 file) đạt; smoke test với API cục bộ xác nhận đúng shape của `/health`, `/ready`, `/me`, `/search`, `/chat`, `/documents`, `/documents/{id}`, `/traces/{id}` và `GET /conversations` trả 405 (nên trang hội thoại dùng chỉ mục cục bộ + đọc lại qua endpoint có phân quyền). Còn thiếu: dev seed cấp user/role/collection/token cho UI, các endpoint review/approve + index manifest + users/roles + audit list (PHASE 5 Admin UI vẫn In Progress), phân trang, chính sách session/token phía trình duyệt và nghiệm thu responsive/accessibility của chủ dự án.
