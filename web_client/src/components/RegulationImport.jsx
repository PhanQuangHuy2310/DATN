import { useRef, useState } from "react";
import { api } from "../api.js";
import { errorText } from "../domain.js";
import { bytesToBase64, IMPORT_ACCEPT, IMPORT_MAX_BYTES, IMPORT_TEMPLATE } from "../regulationImport.js";

/** Nhập văn bản viết sẵn (.txt / .md / .docx): máy chủ trích chữ (không lưu file), đổ vào form rồi AI kiểm tra ngay. */
export default function RegulationImport({ apiBase, onImported, onError }) {
  const input = useRef(null);
  const [busy, setBusy] = useState(false);
  const [lastFile, setLastFile] = useState("");

  const pick = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > IMPORT_MAX_BYTES) {
      onError("File quá lớn (tối đa 2 MB).");
      return;
    }
    setBusy(true);
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const res = await api(`${apiBase}/regulations/import`, {
        method: "POST",
        silent: true,
        body: JSON.stringify({ filename: file.name.slice(0, 200), data_base64: bytesToBase64(bytes) }),
      });
      setLastFile(file.name);
      onImported(res.imported, file.name);
    } catch (err) {
      onError(err?.fields?.file?.[0] || errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const downloadTemplate = () => {
    const url = URL.createObjectURL(new Blob([IMPORT_TEMPLATE], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "mau-quy-dinh.txt";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="reg-import">
      <input ref={input} type="file" accept={IMPORT_ACCEPT} hidden onChange={pick} aria-label="Chọn file quy định" />
      <button type="button" className="btn-secondary" disabled={busy} onClick={() => input.current?.click()}>
        {busy ? "Đang đọc file..." : "Nhập từ file (.txt, .md, .docx)"}
      </button>
      <button type="button" className="btn-link" onClick={downloadTemplate}>Tải file mẫu</button>
      <span className="reg-import-hint">
        {lastFile
          ? `Đã nạp «${lastFile}» vào form; AI đã kiểm tra, xem kết quả bên dưới.`
          : "Viết sẵn mỗi điều một dòng; dòng đầu là tiêu đề, dòng \"Mã:\" và \"Danh mục:\" là tùy chọn."}
      </span>
    </div>
  );
}
