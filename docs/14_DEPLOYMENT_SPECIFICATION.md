# 14. Deployment Specification

## 1. Mục tiêu
Docker Compose trên host Windows/Linux TBD trong LAN; trải nghiệm phát triển Windows/VS Code. Các container/service: API, worker, PostgreSQL, Qdrant, Ollama và frontend/static delivery theo thiết kế triển khai. Không suy ra production OS từ môi trường dev Windows.

## 2. Cấu hình
Profile dev/staging/production TBD; cấu hình qua environment/secret mounts, không commit secret. Pin image/model/version, health checks, persistent volumes, network segmentation và resource limits cần định nghĩa. Model được nạp cục bộ; hướng chuyển model offline TBD.

## 3. Offline/LAN
Runtime không phụ thuộc cloud. Cài mới/cập nhật qua gói đã kiểm tra và chuyển vào LAN theo quy trình chủ dự án duyệt; cần xác minh license và checksum. TLS nội bộ, DNS, firewall, backup target và client access TBD.

## 4. Backup/restore
Phối hợp snapshot/backup PostgreSQL và file assets; ghi manifest/config và phiên bản; Qdrant snapshot tùy khả năng hoặc rebuild từ nguồn chuẩn. Quy trình restore phải bảo đảm consistency và kiểm tra retrieval/citation sau khôi phục. Lịch, retention, encryption, RPO/RTO TBD.

## 5. Quan sát và vận hành
Structured logs, metrics cơ bản, health/readiness, job failure, disk/model/index health; không đưa tài liệu nhạy cảm vào telemetry không kiểm soát. Runbook upgrade, rollback, restore, reindex và incident thuộc Phase 8.

## 6. Chưa chốt
OS host, reverse proxy/TLS, artifact registry offline, resource sizing/GPU, model distribution, HA, backup destination, monitoring stack. Không thêm nền tảng trước quyết định.
