# 17. Decision Log

Quyết định được đánh dấu **Proposed** chưa phải phê duyệt. Chủ dự án là decision owner mặc định; ngày cụ thể được ghi khi chốt.

| ID | Chủ đề | Baseline/đề xuất | Trạng thái | Cần quyết định |
|---|---|---|---|---|
| ADR-001 | Stack | Python/FastAPI, React/TS, PostgreSQL, Qdrant, Ollama, Docker Compose | Accepted (user requirement) | Không đổi nếu chưa có yêu cầu mới |
| ADR-002 | Kiến trúc dịch vụ | Modular monolith + worker riêng | Proposed | Chấp thuận topology và cách deploy worker |
| ADR-003 | Job queue | PostgreSQL-backed queue ở baseline | Open | Thư viện/cơ chế cụ thể; không thêm broker nếu chưa duyệt |
| ADR-004 | File storage | Persistent filesystem volume cho blob gốc/artefact | Open | Filesystem hay object-compatible tự host; backup path |
| ADR-005 | OCR/extraction | Engine local hỗ trợ tiếng Việt; confidence + review | Open | Engine, license, layout/table needs, quality threshold |
| ADR-006 | Parser pháp luật | Parser rule-based + review, lưu confidence/provenance | Proposed | Mức tự động hóa và corpus chuẩn |
| ADR-007 | Embedding/LLM/reranker | Chạy qua Ollama/local model | Open | Model/version, license, RAM/VRAM, tiếng Việt, context |
| ADR-008 | BM25 | Lexical/full-text trong PostgreSQL là phương án đầu | Open | Có chấp nhận built-in lexical hay backend khác trong stack hiện tại |
| ADR-009 | Authentication | Local account là baseline tối thiểu | Open | MFA/SSO/IdP, password policy/session |
| ADR-010 | ACL | RBAC bắt buộc; ACL theo collection/document nếu cần | Open | Phân loại dữ liệu, nhóm người dùng, deny-by-default |
| ADR-011 | Hiệu lực | As-of temporal state; chỉ relation đã xác minh tác động | Proposed | Quy tắc partial amendment/repeal, nguồn xác thực |
| ADR-012 | Vận hành offline | Runtime không cloud; cập nhật qua gói cục bộ | Accepted (user requirement) | Mức air-gap và quy trình chuyển gói |
| ADR-013 | Backup/restore | PostgreSQL + blobs là nguồn khôi phục; vector rebuildable | Proposed | RPO/RTO, retention, encryption, nơi lưu, lịch |
| ADR-014 | Hiệu năng/SLA | Chưa đặt ngưỡng | Open | Users đồng thời, corpus size, latency/availability |
| ADR-015 | Data governance | Chưa chốt retention/chat/audit/deletion | Open | Thời hạn lưu, quyền xóa/ẩn danh, legal hold |
| ADR-016 | Deployment host | Windows dev; host LAN production TBD | Open | OS, GPU, TLS, network segmentation |
| ADR-017 | Security policy | RBAC/audit/secret hygiene bắt buộc | Accepted (user requirement) | Role matrix, encryption/key lifecycle, audit tamper protection |

## Quy tắc cập nhật
Mỗi quyết định mới ghi lựa chọn, bối cảnh, hệ quả, owner và ngày. Khi đổi quyết định, không xóa lịch sử; cập nhật tài liệu bị ảnh hưởng và `PROJECT_STATE.json`.
