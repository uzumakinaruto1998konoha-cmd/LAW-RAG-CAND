"""Khởi chạy ứng dụng LAW-RAG-CAND hoàn chỉnh (Backend API + Web UI).

Sử dụng cấu hình bootstrap chuẩn tại config/bootstrap.example.json.
Tokens được sinh ngẫu nhiên an toàn tại runtime (Rule 5: không hard-code credentials).
Web UI và API được phục vụ đồng thời tại http://127.0.0.1:8000.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Configure utf-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thêm thư mục src vào PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

import uvicorn
from law_rag.api.app import create_app
from law_rag.api.bootstrap import build_container, load_config_file, print_generated_tokens


def main() -> None:
    config_path = ROOT_DIR / "config" / "bootstrap.example.json"
    if not config_path.is_file():
        print(f"Lỗi: Không tìm thấy file cấu hình {config_path}", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print(" KHỞI CHẠY HỆ THỐNG LAW-RAG-CAND (OFFLINE / ON-PREMISE)")
    print("=" * 70)
    print(f"Nạp cấu hình bootstrap từ: {config_path}")

    config = load_config_file(config_path)
    result = build_container(config)

    print("\n--- DANH SÁCH TÀI KHOẢN VÀ BEARER TOKEN TẠI RUNTIME ---")
    print_generated_tokens(result)
    print("Lưu ý: Lưu lại các token trên để đăng nhập trên giao diện Web UI.\n")

    app = create_app(result.container)

    host = os.environ.get("LAW_RAG_API_HOST", "127.0.0.1")
    port = int(os.environ.get("LAW_RAG_API_PORT", "8000"))

    print(f"Hệ thống đang hoạt động tại: http://{host}:{port}")
    print(f"Tài liệu API (OpenAPI/Swagger): http://{host}:{port}/api/v1/docs")
    print(f"Giao diện Web UI (SPA): http://{host}:{port}/")
    print("=" * 70)

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
