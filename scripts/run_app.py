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

    # Lưu token ra file cục bộ để tiện sao chép (đã thêm vào .gitignore)
    token_file = ROOT_DIR / ".law_rag_tokens.txt"
    with open(token_file, "w", encoding="utf-8") as f:
        f.write("# LAW-RAG-CAND RUNTIME TOKENS (TỰ ĐỘNG SINH KHI KHỞI CHẠY)\n")
        f.write("# Dùng các token này để đăng nhập tại: http://127.0.0.1:8000/dev/login\n\n")
        for u in config.users:
            tok = result.tokens.get(u.user_id, "")
            f.write(f"Tài khoản: {u.username} ({u.display_name}) - Vai trò: {', '.join(u.roles)}\n")
            f.write(f"User ID:   {u.user_id}\n")
            f.write(f"Token:     {tok}\n\n")
    print(f"-> Đã lưu danh sách token vào file: {token_file}")
    print("   (Bạn có thể mở file này để sao chép token bất cứ lúc nào)\n")

    # Tự động nạp văn bản pháp luật mẫu vào kho tri thức
    from scripts.seed_data import seed_sample_corpus
    print("Đang nạp văn bản pháp luật mẫu vào kho tri thức...")
    seeded_count = seed_sample_corpus(result.container)
    print(f"-> Đã nạp thành công {seeded_count} văn bản pháp luật mẫu (Luật GTĐB 2024, Luật Căn cước 2023).\n")

    app = create_app(result.container)

    host = os.environ.get("LAW_RAG_API_HOST", "127.0.0.1")
    port = int(os.environ.get("LAW_RAG_API_PORT", "8000"))

    import socket
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        test_sock.bind((host, port))
        test_sock.close()
    except OSError:
        print(f"\n[LỖI] Cổng {port} trên {host} đang bị chiếm dụng bởi tiến trình khác.")
        print(f"Để khắc phục, bạn có thể:")
        print(f"  1. Chạy .\\scripts\\run_dev.ps1 để tự động giải phóng cổng.")
        print(f"  2. Đổi cổng khác qua biến môi trường: $env:LAW_RAG_API_PORT=8080 rồi chạy lại.\n")
        sys.exit(1)

    print(f"Hệ thống đang hoạt động tại: http://{host}:{port}")
    print(f"Tài liệu API (OpenAPI/Swagger): http://{host}:{port}/api/v1/docs")
    print(f"Giao diện Web UI (SPA): http://{host}:{port}/")
    print("=" * 70)

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
