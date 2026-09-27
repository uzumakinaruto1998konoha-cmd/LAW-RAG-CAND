# LAW-RAG-CAND

Hệ thống RAG tra cứu văn bản pháp luật, chạy offline trong LAN. Tài liệu đặc tả nằm ở `docs/`, trạng thái dự án ở `PROJECT_STATE.json`.

## Cài đặt

```powershell
python -m pip install -r requirements.txt
```

## Chạy API (PHASE 5)

```powershell
$env:PYTHONPATH='src'
python -m law_rag.api.main            # mặc định http://127.0.0.1:8000
$env:LAW_RAG_API_PORT='8123'         # đổi cổng nếu cần
```

- OpenAPI: `http://127.0.0.1:8000/api/v1/openapi.json` · Swagger UI: `/api/v1/docs`
- Xác thực: header `Authorization: Bearer <token>`; user/collection/role được cấp qua `ApiContainer` bởi deployment code (không có secret trong source).
- Danh sách endpoint và envelope lỗi: `docs/11_API_SPECIFICATION.md` mục 6.

## Chạy test

```powershell
python -m unittest discover -s tests
```
