# Deployment và vận hành

Repository hiện có Dockerfile/Compose cho API foundation. Đây chưa phải release pack production.

## Cổng trước production

- Rotate mọi credential từng xuất hiện trong Git/history/chat.
- Tạo login tách biệt cho `eas_api`, `eas_worker`, migration và privacy.
- Pin image bằng digest; tạo SBOM và chạy dependency/secret/image scan.
- Cài reverse proxy/TLS, private storage/scanner, worker và telemetry.
- Chạy staging tương đương production, load profile, backup/restore và rollback rehearsal.
- Ghi image digest, config release IDs, backup point và actual test evidence vào biên bản G4/G5.

Không dùng `docker-compose.yml` development làm bằng chứng production. Không đưa secret vào Compose, CI variables output hoặc image layer.
