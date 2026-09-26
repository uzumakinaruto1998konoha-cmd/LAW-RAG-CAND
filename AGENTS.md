# LAW-RAG-CAND DEVELOPMENT RULES

## 1. Source of Truth

Các tài liệu sau là nguồn sự thật của dự án:

- `docs/01_PROJECT_MASTER_PLAN.md`
- `docs/02_REQUIREMENTS.md`
- `docs/03_SYSTEM_ARCHITECTURE.md`
- `docs/04_LEGAL_RAG_SPECIFICATION.md`
- `docs/05_DOCUMENT_INGESTION_SPECIFICATION.md`
- `docs/06_LEGAL_DATA_MODEL.md`
- `docs/07_CHUNKING_SPECIFICATION.md`
- `docs/08_RETRIEVAL_SPECIFICATION.md`
- `docs/09_CITATION_SPECIFICATION.md`
- `docs/10_SECURITY_SPECIFICATION.md`
- `docs/11_API_SPECIFICATION.md`
- `docs/12_UI_SPECIFICATION.md`
- `docs/13_TESTING_SPECIFICATION.md`
- `docs/14_DEPLOYMENT_SPECIFICATION.md`
- `docs/15_ROADMAP.md`
- `docs/16_TASK_BOARD.md`
- `docs/17_DECISION_LOG.md`
- `docs/18_CHANGE_LOG.md`
- `PROJECT_STATE.json`

## 2. Không tự ý thay đổi kiến trúc

Mọi thay đổi kiến trúc phải:

1. Ghi vào `docs/17_DECISION_LOG.md`.
2. Cập nhật tài liệu kiến trúc `docs/03_SYSTEM_ARCHITECTURE.md` và các tài liệu liên quan.
3. Cập nhật `PROJECT_STATE.json`.

## 3. Task Discipline

Chỉ thực hiện task được yêu cầu.

Không tự động làm các task tiếp theo.

Sau khi hoàn thành thay đổi được yêu cầu, tạo commit Git với message mô tả rõ thay đổi và push lên remote `origin`. Không commit hoặc push các thay đổi không liên quan của người dùng; nếu workspace có thay đổi ngoài task, báo rõ và chỉ commit phần thuộc task. Nếu commit/push thất bại, giữ thay đổi an toàn và báo nguyên nhân.

## 4. Testing

Code mới phải có test.

Không được đánh dấu task hoàn thành nếu test chưa đạt.

## 5. Security

Không hard-code:

- password
- API key
- token
- secret

## 6. Legal Knowledge

Không được hard-code nội dung pháp luật vào source code.

Tài liệu pháp luật phải đi qua Document Ingestion Engine.

## 7. RAG

Không cho LLM trả lời dựa trên kiến thức tự sinh khi không có context phù hợp.

## 8. Citation

Câu trả lời pháp luật phải có nguồn.

## 9. Offline

Không thêm dependency cloud/API bên ngoài nếu chưa được phê duyệt.
