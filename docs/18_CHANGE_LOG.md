# 18. Change Log

## 2026-09-26 — Phase 0 initial specification
- Tạo bộ 18 tài liệu kế hoạch/đặc tả và `PROJECT_STATE.json` theo yêu cầu.
- Xác lập stack baseline đúng yêu cầu; ghi rõ đề xuất kiến trúc modular monolith + worker và các quyết định còn mở.
- Chưa tạo mã nguồn, chưa thêm framework/dịch vụ, chưa dùng API cloud.
- Rà soát chéo: requirement, dependency, conflict và TBD được ghi trong tài liệu tương ứng.

## 2026-09-26 — Phase 0 approval and Phase 1 ingestion design
- Ghi nhận project owner approval Phase 0 theo yêu cầu trong phiên; mở PHASE 1.
- Hoàn tất task thiết kế ingestion đầu tiên: định dạng/giới hạn v1, extraction/OCR local, filesystem storage, review threshold và corpus manifest.
- Cập nhật ADR-004..006, kiến trúc, testing spec, task board và project state. Chưa tạo code hay cài dependencies; task tiếp theo là ingestion engine.

## 2026-09-26 — Phase 1 ingestion engine
- Thêm lõi upload/validation/hash, filesystem content-addressed storage, exact dedup/idempotency, trạng thái/retry job, PostgreSQL DB-API adapter, migration và audit sink.
- Thêm unit tests cho định dạng, giới hạn, lỗi, storage/job lifecycle; 14 test đạt. Không cài dependency ngoài.
- Chốt ADR-003 dùng bảng PostgreSQL không broker; cập nhật kiến trúc, TASK_BOARD và PROJECT_STATE. Task tiếp theo: extraction/OCR.

## 2026-09-26 — Phase 1 extraction
- Thêm trích xuất PDF (page/text/bbox, mixed scan OCR), DOCX paragraph/table/source locator, UTF-8 text và JPG/PNG OCR; lưu confidence, tool versions, traineddata SHA-256, pipeline version và review warnings.
- Pin PyMuPDF 1.28.2, python-docx 1.2.0, Pillow 12.3.0; yêu cầu Tesseract 5.5.3 + `vie`. Project owner chấp thuận PyMuPDF AGPL v3 cho triển khai nội bộ. Không tải/cài package hay binary trong task.
- 26 unit tests và compile check đạt. Tesseract chưa có trên máy hiện tại; OCR được kiểm tra bằng adapter giả và đường thiếu-engine/review, cần chạy golden corpus OCR trong môi trường đã đóng gói binary/model.
- Cập nhật ADR-005, đặc tả ingestion, kiến trúc, deployment/testing spec, task board và project state. Task tiếp theo: legal parsing.

## 2026-09-27 — Phase 1 legal parsing
- Thêm rule-based legal parser (`legal_rules`, `legal_parsing`): ghép span thành dòng đọc, dựng cây CHAPTER/SECTION/ARTICLE/CLAUSE/POINT/APPENDIX, trích metadata và nhận diện ứng viên quan hệ; mọi giá trị có provenance (page/locator/detector), confidence, raw value và mã cảnh báo ổn định.
- Thêm workflow review (`legal_review`): quyết định accept/correct/reject theo metadata/node/relation, lưu reviewer và thời điểm, audit từng quyết định; chỉ duyệt khi không còn item pending và mọi warning đã được acknowledge.
- Thêm adapter PostgreSQL và `migrations/0002_legal_parsing.sql` (legal_parse_run, legal_node, metadata_assertion, document_relation_candidate, review_decision, document_approval); không thêm driver.
- Thêm 29 unit tests (parse từ DOCX thật, cây node, metadata, quan hệ, review gate, adapter); 55 test toàn repo đạt. Không thêm dependency, không nhúng nội dung luật vào source.
- Cập nhật ADR-006, docs/05, docs/06, docs/13, task board và project state. Task tiếp theo: release to KB (approval, dedup, version, processing run).

## 2026-09-27 — Phase 1 release to knowledge base
- Thêm `migrations/0003_release_to_kb.sql`: schema cho document identity (unique document_number + issuing_body + document_type), document_version (immutable snapshot với version_number, dates, content_hash), document_relation (verified relations), processing_run (release/index operations tracking), version_processing_record (audit trail), và duplicate_candidate (near-duplicate detection).
- Thêm domain models `kb_models.py`: Document, DocumentVersion, DocumentRelation, ProcessingRun, VersionProcessingRecord, DuplicateCandidate với validation logic và temporal properties.
- Thêm PostgreSQL adapter `kb_postgres.py`: KnowledgeBaseRepository với CRUD operations cho tất cả KB entities, support document versioning và duplicate tracking.
- Thêm service layer `kb_release.py`: ReleaseService orchestrate approved documents sang retrievable KB, tạo/update document identity, increment version numbers, compute content hash cho deduplication, track processing runs, và transition job status sang INDEXING.
- Thêm ReleaseError vào `errors.py`.
- Thêm 18 unit tests `test_kb_models.py` cho domain model validation; 73 tests toàn repo đạt. Không thêm dependency.
- Design: Document identity enforced bởi unique constraint; versions không tự động supersede (admin quản lý); content-based dedup qua SHA-256 của nodes+metadata; chỉ approved documents được release; processing runs có manifest và error tracking.
- Cập nhật task board và project state. Task tiếp theo: PHASE 2 knowledge model hoặc tiếp tục PHASE 1 corpus testing.

## 2026-09-27 — Phase 2 knowledge model and ACL
- Thêm `migrations/0004_knowledge_model_acl.sql`: RBAC schema với app_user, role, permission, user_role, role_permission; document collections cho ACL scoping (document_collection, collection_access, document_collection_member); session management (user_session, password_reset_token); validity_status field cho document_version.
- Default roles theo docs/10: system_admin, knowledge_admin, reviewer, user, auditor với permissions matrix.
- Default permissions: document operations (upload/view/view_restricted/edit_metadata/approve/delete), version/relation/user/role/audit/index/collection management.
- Thêm domain models `knowledge_models.py`: AppUser, Role, Permission, UserRole, DocumentCollection, CollectionAccess, UserSession, PasswordResetToken, ValidityStatus enum, AccessLevel enum.
- Thêm service layer `authorization.py`: AuthorizationService với permission checks, collection/document access validation, và AuditLogger cho access audit trail.
- Thêm 27 unit tests `test_knowledge_model.py` cho RBAC/ACL/temporal features; 100 tests toàn repo đạt. Không thêm dependency.
- Design: RBAC với role-based permissions; collection-based ACL cho document access; temporal role assignments với expiry; validity status tracking cho effective dates; session management với expiry/revocation.
- Cập nhật task board và project state. Task tiếp theo: Knowledge UI/API implementation hoặc PHASE 3 Index.

## 2026-09-27 — Phase 3 index infrastructure and chunking
- Thêm `migrations/0005_index_retrieval.sql`: Schema cho chunking (chunk_set, chunk với structural path preservation), index manifests (index_manifest, chunk_index_record), retrieval traces (retrieval_trace, retrieval_result), và search metrics.
- Thêm domain models `retrieval/models.py`: ChunkSet, Chunk, IndexManifest, RetrievalTrace, RetrievalResult với enums IndexType/IndexStatus/QueryType/RetrievalMethod.
- Thêm service `retrieval/chunking.py`: ChunkingService generate chunks từ legal nodes ở article/clause/point level, preserve structural path (Chương/Mục/Điều), maintain page spans và provenance.
- Chunk strategy theo docs/07: legal boundaries ưu tiên hơn token length; chunk ở cấp Điều khi phù hợp; giữ structural path, heading, page locations.
- Index manifest versioning: support BUILDING/READY/ACTIVE/FAILED/RETIRED states; track embedding model, lexical analyzer, chunk/document counts; reproducible builds.
- Retrieval traces: audit trail cho mọi search query với user_id, query type, filters, as_of_date, result count, latency.
- Thêm 16 unit tests `test_retrieval.py` cho chunking/indexing models; 116 tests toàn repo đạt. Không thêm dependency.
- Design: Legal-aware chunking với boundary preservation; manifest lifecycle cho index versioning; retrieval audit trail; chuẩn bị cho hybrid search (BM25 + vector).
- Cập nhật task board và project state. Task tiếp theo: PHASE 3 retrieval implementation (hybrid search, fusion, ACL filtering) hoặc PHASE 4 RAG.

## 2026-09-27 — Phase 4 RAG and citations
- Thêm `migrations/0006_rag_citations.sql`: Schema cho conversations (conversation, message), evidence tracking (evidence, citation, message_warning), và RAG metrics.
- Thêm domain models `rag/models.py`: Conversation, Message, Evidence, Citation, RAGResponse với enums MessageRole/CitationStatus.
- Thêm service `rag/service.py`: RAGService cho grounded answer generation, insufficient evidence detection, server-side citation generation.
- RAG pipeline per docs/04: Evidence → Context → LLM (Ollama) → Grounded answer → Citation validation → Response.
- Insufficient evidence handling: Clear indication when no evidence found, warnings about unverified/invalid documents.
- Citation generation: Server-side only from evidence IDs (no hallucinated citations per docs/04 section 4).
- Conversation management: Track conversation threads, message history, and retrieval traces.
- Warning system: Document unverified status, validity status, missing as_of_date.
- Thêm 15 unit tests `test_rag.py` cho RAG models and service; 131 tests toàn repo đạt. Không thêm dependency.
- Design: Grounded answer generation với explicit evidence citations; separation of "what document says" vs "interpretation"; ACL filtering at retrieval layer.
- Cập nhật task board và project state. Task tiếp theo: Complete PHASE 3 retrieval hoặc PHASE 5 UI development.

## 2026-09-27 — Phase 3 hybrid retrieval engine
- Thêm `retrieval/search.py`: Triển khai đầy đủ công cụ tìm kiếm kết hợp (BM25Okapi lexical search + vector cosine similarity search).
- Thuật toán hợp nhất (Fusion algorithms): Reciprocal Rank Fusion (RRF) k=60 và Weighted Score Fusion với min-max normalization.
- Kiểm soát truy cập ACL phía server (Server-side ACL filtering): Loại bỏ hoàn toàn tài liệu ngoài quyền của user trước khi xếp hạng (ACL leakage = 0).
- Bộ lọc thời gian và hiệu lực (Temporal & validity filtering): Đánh giá `as_of_date` và `validity_status`, ưu tiên văn bản còn hiệu lực (`in_force`), hạ điểm hoặc cảnh báo văn bản đã hết hiệu lực (`repealed`).
- Bộ xếp hạng lại cấu trúc pháp luật (LegalReranker): Tăng trọng số cho kết quả khớp chính xác số hiệu văn bản, Điều/Khoản và tiêu đề mục.
- Kiểm toán truy xuất (Audit trace): Lưu vết toàn bộ truy vấn trong `RetrievalTrace` và chi tiết `RetrievalResult`.
- Chuyển đổi kết quả tìm kiếm thành danh sách `Evidence` chuẩn hoá sẵn sàng cho `RAGService`.
- Sửa lỗi thuộc tính `is_locked` trong `tests/test_knowledge_model.py` so sánh thời gian động.
- Thêm 12 unit tests trong `tests/test_retrieval_engine.py`; toàn bộ 143 tests pass (100%). Không thêm dependency bên ngoài.

## 2026-09-27 — Phase 5 API backend (FastAPI `/api/v1`)
- Thêm package `src/law_rag/api/`: `app.py` (application factory `/api/v1`, OpenAPI là contract), `container.py` (service graph + enforcement point), `dependencies.py`, `errors.py`, `security.py`, `acl.py`, `schemas.py`, `routers/` (health, identity, search, chat, documents, ingestion), `main.py` (chạy bằng `python -m law_rag.api.main`).
- Endpoint: `GET /health`, `GET /ready`, `GET /me`, `POST /search`, `POST /chat`, `POST /conversations`, `GET /conversations/{id}`, `GET /documents`, `GET /documents/{id}`, `POST /documents/upload`, `GET /jobs/{id}`, `GET /traces/{id}`.
- Xác thực server-side bằng bearer token opaque; registry chỉ giữ SHA-256 token, không log token. RBAC deny-by-default theo ma trận 5 vai trò, ghi đè được khi triển khai.
- ACL collection deny-by-default nối vào `AuthorizationService.check_collection_access` mà retrieval gọi trước ranking: mọi đường đọc (search, chat, documents, job, trace) đều lọc ACL; tài liệu/hội thoại/job của người khác trả 404 để không lộ sự tồn tại.
- Envelope lỗi chuẩn với mã ổn định, `request_id` (header `X-Request-ID` echo), field errors; 5xx trả thông điệp chung không kèm stack trace hay secret, và log 5xx chỉ ghi `error_type` (không sao chép nội dung exception vào log). Middleware gán request id cho mọi response.
- Ghi nhận hành vi framework: FastAPI giải mã body JSON trước dependency nên body hỏng trả 422 trước 401; đã có test khoá lại hành vi này và ghi vào `docs/11`.
- Upload dùng body thô + `filename` query + `Idempotency-Key`; kiểm tra giới hạn kích thước khi đọc stream (413 trước khi ghi blob), trùng nội dung trả `duplicate_match`, `document_id`/`version_id` là null tới khi version được duyệt.
- Thêm adapter in-memory `ingestion/memory.py` cho dev/test (production vẫn dùng PostgreSQL theo ADR-003) và projection chỉ đọc trên `RetrievalService` cho lớp knowledge.
- Pin `fastapi==0.141.1`, `uvicorn==0.54.0`, `httpx==0.28.1` (test) trong `requirements.txt`.
- Thêm 46 test trong `tests/test_api.py` (authn 401, RBAC 403, ACL leakage = 0, chat có citation, insufficient evidence, ownership hội thoại, upload/duplicate/413/415/409/503, trace audit, envelope 500 an toàn cả response lẫn log); toàn bộ 189 tests pass (100%).
- Cập nhật ADR-018 (API layer) và trạng thái ADR-009/ADR-010, đặc tả API, task board và project state. Task tiếp theo: PHASE 5 Web UI hoặc benchmark corpus.

## 2026-09-29 — Phase 5 Web app (React/Vite) dựng đủ màn hình và build/lint/test đạt
- Thêm 7 màn hình còn thiếu: `ChatPage` (câu trả lời có dẫn chiếu, evidence, cảnh báo, trạng thái “không đủ căn cứ”, trạng thái thiếu quyền), `ConversationsPage`, `DocumentListPage`, `DocumentDetailPage`, `TracePage`, `AdminPage`, `HealthPage`; hoàn thiện `SearchPage` (query_type, bộ lọc metadata, link trace, link chi tiết tài liệu, chat tiếp từ câu hỏi).
- Sửa các lỗi chặn build: `AuthProvider` chưa được gắn trong `main.tsx` (mọi `useAuth` sẽ ném lỗi khi chạy), `shared/ui/index.ts` trỏ sai `./ToastProvider`, `features/auth` import `../ui` sai đường dẫn, `useChat` thiếu import `get`, tuỳ chọn `onError` của `useQuery` đã bị react-query v5 bỏ, `AppShell` bắt buộc prop `children` trong khi route dùng layout, và thiếu CSS entry Tailwind.
- Thêm hạ tầng trình bày dùng chung: `shared/format.ts` (ngày, số trang, điểm, dung lượng, nhãn trạng thái job/citation có fallback nguyên văn), `shared/conversations.ts` (chỉ mục hội thoại cục bộ trong trình duyệt), `shared/ui/{Panel,PageHeader,Warnings,PermissionDenied}.tsx`, hook `useHealth`/`useReadiness` và `useIngestion` (upload body thô + `Idempotency-Key` sinh tại runtime + poll job tới trạng thái kết thúc).
- Thêm `src/index.css` (`@tailwind`), `public/favicon.svg`, `frontend/.gitignore`; tách `features/auth/authContext.ts` + `AuthProvider.tsx` và `shared/ui/toastContext.ts` để `useToast` gọi được như hàm và tuân thủ rule react-refresh.
- Bảo mật/đúng quy tắc: trang đăng nhập không còn hard-code danh sách token mẫu (AGENTS §5, docs/10) — chỉ hướng dẫn lấy token từ deployment/test harness; UI không nhúng nội dung pháp luật, danh mục lọc lấy từ dữ liệu server; quyền chỉ được ẩn/khóa ở UI, server vẫn quyết định cuối cùng.
- UI nêu rõ các năng lực chưa có endpoint trong `/api/v1` (duyệt/release, index manifest, users/roles, audit list, backup) thay vì giả lập thao tác thành công.
- Thêm test tooling cục bộ Vitest 5 + React Testing Library 16 + jsdom, `vitest.config.ts`, script `npm test`/`npm run test:watch`; 36 test trong 9 file (format, chỉ mục hội thoại, envelope lỗi, SearchPage, ChatPage, DocumentListPage, AdminPage, HealthPage, TracePage). Chuyển `eslint.config.js` sang flat config chạy được (thêm `@eslint/js`, `typescript-eslint`, `globals`); `npm run lint` 0 lỗi/warning, `npm run build` (tsc -b + vite build) đạt, lock dependency vào `package-lock.json`.
- Smoke test với API cục bộ (container in-memory, 1 tài liệu tổng hợp, token sinh tại runtime): `/health`, `/ready` (degraded vì ingestion chưa wiring), `/me`, `/search`, `/chat` (có citation `valid`), `/documents`, `/documents/{id}`, `/traces/{id}` trả đúng shape mà UI dựng theo; `GET /conversations` trả 405 xác nhận chưa có endpoint liệt kê hội thoại; 401 khi thiếu token.
- Cập nhật ADR-019 (web app layer), task board (Web app Done, Admin UI In Progress), project state. Chưa chạy được test Python trong phiên này (môi trường không có pytest) nên không xác minh lại 189 test backend.
- Task tiếp theo: chạy benchmark corpus đã duyệt, hoặc mở endpoint review/approve + index manifest để hoàn tất PHASE 5 Admin UI.

