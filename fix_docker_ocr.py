"""Sửa riêng bước preload PaddleOCR trong ai_service/Dockerfile.
Chạy: python fix_docker_ocr.py (tại thư mục gốc DATN)
Giữ nguyên các chỉnh sửa khác của Dockerfile, bao gồm bước pip install.
"""
from pathlib import Path
import sys

p = Path('ai_service/Dockerfile')
if not p.exists():
    sys.exit('Không tìm thấy ai_service/Dockerfile. Hãy chạy từ thư mục gốc DATN.')

src = p.read_text(encoding='utf-8')
if 'ARG PRELOAD_OCR_MODELS=false' in src:
    print('Đã có cấu hình bỏ tải OCR khi build. Không thay đổi file.')
    sys.exit(0)

start_marker = '# Pre-download the Vietnamese OCR models into the image'
end_marker = '# ---------------------------------------------------------------------------\n# Stage 2 — runtime:'
if start_marker not in src or end_marker not in src:
    sys.exit('Không nhận ra cấu trúc Dockerfile hiện tại, không sửa để tránh hỏng file.')

start = src.index(start_marker)
end = src.index(end_marker, start)

replacement = '''# Do not initialize PaddleOCR during Docker build (avoids SIGBUS on Docker Desktop).
# PaddleOCR is still installed. Models will be downloaded on first OCR use
# and persisted in the ai_ocr_models named Docker volume.
ARG PRELOAD_OCR_MODELS=false
RUN mkdir -p /root/.paddlex \\
    && if [ "$ENABLE_PADDLE_OCR" = "true" ] && [ "$PRELOAD_OCR_MODELS" = "true" ]; then \\
         python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='vi', device='cpu', use_textline_orientation=True, use_doc_orientation_classify=False, use_doc_unwarping=False, enable_mkldnn=False)"; \\
       fi \\
    && find /opt/venv -name '__pycache__' -type d -prune -exec rm -rf {} +

'''

p.write_text(src[:start] + replacement + src[end:], encoding='utf-8')
print('Đã sửa ai_service/Dockerfile (chỉ đoạn OCR).')
print('Các thay đổi trước đó, bao gồm cài pip, được giữ nguyên.')
