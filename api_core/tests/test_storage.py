from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from api_core.storage import StorageError, scan_with_clamav, sniff_allowed_mime


class StorageSecurityTests(SimpleTestCase):
    def test_sniffs_content_instead_of_trusting_extension(self):
        self.assertEqual(sniff_allowed_mime(b"%PDF-1.7\n"), "application/pdf")
        self.assertEqual(sniff_allowed_mime(b"\x89PNG\r\n\x1a\nrest"), "image/png")
        self.assertEqual(sniff_allowed_mime(b"\xff\xd8\xffrest"), "image/jpeg")
        with self.assertRaisesRegex(StorageError, "FILE_TYPE_NOT_ALLOWED"):
            sniff_allowed_mime(b"MZ executable renamed invoice.pdf")

    @override_settings(EAS_CLAMAV_HOST="scanner", EAS_CLAMAV_PORT=3310)
    @patch("api_core.storage.socket.create_connection")
    def test_scanner_fails_closed_for_malware_and_outage(self, connect):
        scanner = MagicMock()
        scanner.__enter__.return_value = scanner
        scanner.recv.return_value = b"stream: Eicar-Test-Signature FOUND\0"
        connect.return_value = scanner
        with self.assertRaisesRegex(StorageError, "MALWARE_DETECTED"):
            scan_with_clamav(b"unsafe")

        connect.side_effect = OSError("offline")
        with self.assertRaisesRegex(StorageError, "MALWARE_SCANNER_UNAVAILABLE"):
            scan_with_clamav(b"unknown")
