"""Generate the synthetic invoice images used by the OCR smoke test.

All companies, tax codes and amounts are invented; no real data. Run once and
commit the PNGs: python tests/ocr_smoke/generate_invoices.py <font.ttf>
(any font with Vietnamese glyphs, e.g. DejaVuSans.ttf or Arial).
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
INVOICES = [
    {
        "file": "invoice_vat.png",
        "lines": [
            "CÔNG TY TNHH THƯƠNG MẠI ĐẠI PHÁT",
            "MST: 0312345678",
            "HÓA ĐƠN GIÁ TRỊ GIA TĂNG",
            "Số hóa đơn: 0001234",
            "Ngày 15 tháng 03 năm 2026",
            "Văn phòng phẩm   2   250.000 VND",
            "Thành tiền: 500.000 VND",
            "Tổng cộng thanh toán: 1.540.000 VND",
        ],
        "expected": {
            "amount": 1540000,
            "invoice_date": "2026-03-15",
            "vendor_name": "Thương Mại Đại Phát",
        },
    },
    {
        "file": "receipt_service.png",
        "lines": [
            "CÔNG TY CỔ PHẦN DỊCH VỤ ÂU LẠC",
            "BIÊN LAI THU TIỀN",
            "Ngày 02/11/2026",
            "Dịch vụ vệ sinh văn phòng",
            "Tổng tiền: 320.000 VND",
        ],
        "expected": {
            "amount": 320000,
            "invoice_date": "2026-11-02",
            "vendor_name": "Dịch Vụ Âu Lạc",
        },
    },
    {
        "file": "invoice_supplies.png",
        "lines": [
            "CÔNG TY TNHH MTV KHÁNH HƯNG",
            "MST: 0109876543",
            "HÓA ĐƠN BÁN HÀNG",
            "Ngày 28/10/2026",
            "Giấy in A4   10 ram   85.000 VND",
            "Tổng cộng: 850.000 VND",
        ],
        "expected": {
            "amount": 850000,
            "invoice_date": "2026-10-28",
            "vendor_name": "Khánh Hưng",
        },
    },
]


def render(lines, font_path):
    font = ImageFont.truetype(font_path, 34)
    image = Image.new("RGB", (1100, 90 + 62 * len(lines)), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((50, 45 + 62 * index), line, fill="black", font=font)
    return image


def main(font_path):
    for invoice in INVOICES:
        render(invoice["lines"], font_path).save(HERE / invoice["file"])
    expected = {i["file"]: i["expected"] for i in INVOICES}
    (HERE / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(INVOICES)} invoices to {HERE}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "DejaVuSans.ttf")
