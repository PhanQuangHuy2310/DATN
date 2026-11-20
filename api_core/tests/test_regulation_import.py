"""Nhập file quy định viết sẵn (20/11): .txt/.md/.docx -> văn bản trong form; loại file theo magic bytes, không lưu file."""

import base64
import io
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from api_core.administration.regulation_import import ImportError_, extract_regulation

TEXT = (
    "QUY ĐỊNH VỀ NGHỈ PHÉP\n"
    "Mã: qd-np-01\n"
    "Danh mục: Thời gian & Nghỉ phép\n"
    "\n"
    "Điều 1: Yêu cầu Nghỉ phép từ 5 ngày trở lên bắt buộc Trưởng bộ phận phê duyệt thủ công.\n"
    "Điều 2: Yêu cầu Thanh toán chi phí có giá trị dưới 2 triệu đồng được tự động duyệt.\n"
)


def _docx(paragraphs):
    body = "".join(
        f'<w:p><w:pPr/><w:r><w:t xml:space="preserve">{p[:10]}</w:t></w:r><w:r><w:t>{p[10:]}</w:t></w:r></w:p>'
        for p in paragraphs
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
        f'wordprocessingml/2006/main"><w:body>{body}<w:p/></w:body></w:document>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


class ExtractTests(SimpleTestCase):
    def test_text_file_with_title_code_and_category(self):
        r = extract_regulation(TEXT.encode("utf-8"))
        self.assertEqual(r["title"], "QUY ĐỊNH VỀ NGHỈ PHÉP")
        self.assertEqual(r["code"], "QD-NP-01")
        self.assertEqual(r["category"], "Thời gian & Nghỉ phép")
        self.assertEqual(r["articles"], 2)
        self.assertTrue(r["content"].startswith("Điều 1:"))
        self.assertEqual(r["source"], "text")

    def test_utf8_bom_utf16_and_markdown(self):
        self.assertEqual(
            extract_regulation(b"\xef\xbb\xbf" + TEXT.encode())["articles"], 2
        )
        self.assertEqual(extract_regulation(TEXT.encode("utf-16"))["code"], "QD-NP-01")
        md = "# Quy định thanh toán\n\n- **Điều 1:** Yêu cầu Thanh toán chi phí dưới 2 triệu đồng được tự động duyệt.\n"
        r = extract_regulation(md.encode())
        self.assertEqual(r["title"], "Quy định thanh toán")
        self.assertEqual(
            r["content"],
            "Điều 1: Yêu cầu Thanh toán chi phí dưới 2 triệu đồng được tự động duyệt.",
        )

    def test_docx_paragraphs_and_split_runs(self):
        data = _docx(
            [
                "Quy định về nghỉ phép &amp; thanh toán",
                "Điều 1: Yêu cầu Nghỉ phép từ 5 ngày trở lên bắt buộc Trưởng bộ phận phê duyệt thủ công.",
            ]
        )
        r = extract_regulation(data)
        self.assertEqual(r["source"], "docx")
        self.assertEqual(r["title"], "Quy định về nghỉ phép & thanh toán")
        self.assertEqual(r["articles"], 1)
        self.assertIn("Trưởng bộ phận phê duyệt thủ công", r["content"])

    def test_type_is_decided_by_content_not_extension(self):
        for data in (
            b"%PDF-1.7 ...",
            b"\x89PNG\r\n\x1a\n\x00\x00",
            b"\xd0\xcf\x11\xe0legacy-doc",
            b"MZ\x90\x00",
        ):
            with self.assertRaises(ImportError_) as ctx:
                extract_regulation(data)
            self.assertEqual(str(ctx.exception), "FILE_TYPE_NOT_ALLOWED")
        # ZIP that is not a Word document (xlsx, plain zip)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("xl/workbook.xml", "<x/>")
        with self.assertRaises(ImportError_):
            extract_regulation(buf.getvalue())

    def test_limits_and_empty(self):
        for data, code in (
            (b"", "FILE_EMPTY"),
            (b"a" * (2 * 1024 * 1024 + 1), "FILE_TOO_LARGE"),
            ("Chỉ có tiêu đề".encode(), "NO_CONTENT"),
            (
                b"Ti\xeau \xf0\xea\nDi\xeau 1: x",
                "TEXT_NOT_UTF8",
            ),  # ANSI, không phải UTF-8
        ):
            with self.assertRaises(ImportError_) as ctx:
                extract_regulation(data)
            self.assertEqual(str(ctx.exception), code)

    def test_zip_bomb_document_is_refused(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(
                "word/document.xml", "<w:p>" + "a" * (9 * 1024 * 1024) + "</w:p>"
            )
        with self.assertRaises(ImportError_) as ctx:
            extract_regulation(buf.getvalue())
        self.assertEqual(str(ctx.exception), "FILE_TOO_LARGE")


def _actor(*roles):
    return SimpleNamespace(
        id="u-1",
        email="admin@eas.com",
        display_name="Admin",
        roles=frozenset(roles),
        must_change_password=False,
    )


class ImportViewTests(SimpleTestCase):
    def _post(self, data: bytes, roles=("OPS_ADMIN",)):
        with (
            patch(
                "api_core.authn.service.load_actor_from_session",
                return_value=_actor(*roles),
            ),
            patch("api_core.maintenance.is_maintenance_active", return_value=False),
        ):
            return self.client.post(
                "/api/v1/admin/regulations/import",
                data={
                    "filename": "quy-dinh.txt",
                    "data_base64": base64.b64encode(data).decode(),
                },
                content_type="application/json",
            )

    def test_returns_extracted_text_without_storing(self):
        res = self._post(TEXT.encode())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["imported"]["code"], "QD-NP-01")

    def test_binary_renamed_to_txt_is_rejected(self):
        res = self._post(b"%PDF-1.4 fake")
        self.assertEqual(res.status_code, 422)
        self.assertIn("file", res.json()["error"]["fields"])

    def test_employee_without_admin_role_is_forbidden(self):
        res = self._post(TEXT.encode(), roles=("EMPLOYEE",))
        self.assertEqual(res.status_code, 403)
