# Deployment & Infrastructure

Thư mục này chứa các kịch bản (scripts) và tệp cấu hình phục vụ cho việc **triển khai (Deploy)** và vận hành hệ thống.

Bao gồm:
- Các tệp cấu hình Docker (`Dockerfile`, `docker-compose.yml`) cho các môi trường khác nhau.
- Cấu hình CI/CD pipelines (GitHub Actions, GitLab CI, Jenkins...).
- Kubernetes manifests (Deployment, Service, Ingress...) nếu sử dụng K8s.
- Infrastructure as Code (Terraform, Ansible) để tự động hóa việc khởi tạo máy chủ, thiết lập môi trường.
- Các script sao lưu (backup), phục hồi (restore) cơ sở dữ liệu và vận hành hệ thống định kỳ.
