import { useState } from "react";
import { api } from "../api.js";
import { date, types } from "../domain.js";
import { Badge, Data, ResourceState, useResource } from "./ui.jsx";
import { PageControls } from "./ux.jsx";

/** UC05/UC15: a read-only auditor workspace. The API applies department/type
 * scope and deliberately never returns draft payloads to unrelated auditors.
 */
export default function AuditorWorkspace({ onOpen }) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [checked, setChecked] = useState(null);
  const [error, setError] = useState("");
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (search) params.set("q", search);
  const resource = useResource(`/api/v1/requests?${params.toString()}`);
  async function verify(id) {
    setError("");
    setChecked(null);
    try {
      const result = await api(`/api/v1/requests/${id}/audit/verify`);
      setChecked({ id, result });
    } catch (err) {
      setError(err.message || "Không thể kiểm tra chuỗi audit.");
    }
  }
  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">KIỂM TOÁN HỆ THỐNG</p>
          <h1>Tra cứu và xác minh kiểm toán</h1>
          <p className="muted">Chế độ chỉ đọc; danh sách được Backend giới hạn theo vai trò, loại hồ sơ và phòng ban có hiệu lực.</p>
        </div>
      </header>
      <section className="panel audit-scope-banner" aria-label="Nguyên tắc kiểm toán">
        <strong>Kiểm soát quyền đọc</strong>
        <p>Hồ sơ chưa gửi chỉ chủ sở hữu được đọc. Kiểm toán viên không thực hiện phê duyệt, phân công, chỉnh sửa hoặc nghiệm thu. Không coi kết quả kiểm tra thiếu checkpoint là PASS.</p>
      </section>
      <section className="panel filter-panel">
        <form className="audit-search" onSubmit={(e) => { e.preventDefault(); setOffset(0); setSearch(query.trim()); setChecked(null); }}>
          <label>Tìm mã hồ sơ trong phạm vi được phép
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="REQ-2026..." maxLength={100}/>
          </label>
          <button type="submit">Tra cứu</button>
          <button type="button" className="secondary" onClick={() => {setQuery(""); setSearch(""); setOffset(0); setChecked(null);}}>Đặt lại</button>
        </form>
      </section>
      <section className="panel" id="audit-results">
        <div className="section-head"><h2>Hồ sơ có thể kiểm toán</h2><small className="muted">Chọn một hồ sơ để xem revision và lịch sử theo quyền thực tế</small></div>
        <ResourceState resource={resource}>
          {resource.data?.items?.length ? <div className="table-wrap"><table className="responsive-records">
            <thead><tr><th>Mã yêu cầu</th><th>Loại</th><th>Trạng thái</th><th>Cập nhật</th><th>Kiểm tra</th></tr></thead>
            <tbody>{resource.data.items.map((item) => <tr key={item.id}>
              <td data-label="Mã">{item.code}</td><td data-label="Loại">{types[item.type_code] || item.type_code}</td>
              <td data-label="Trạng thái"><Badge value={item.status}/></td><td data-label="Cập nhật">{date(item.updated_at)}</td>
              <td data-label="Thao tác"><div className="actions"><button type="button" className="secondary" onClick={() => onOpen(item.id, "audit")}>Xem hồ sơ</button><button type="button" onClick={() => verify(item.id)}>Xác minh</button></div></td>
            </tr>)}</tbody></table></div> : <p className="empty">Không có hồ sơ trong phạm vi tra cứu hiện tại.</p>}
          <PageControls offset={offset} limit={limit} count={resource.data?.items?.length || 0} nextOffset={resource.data?.next_offset} onPage={setOffset} onLimit={(n) => {setLimit(n);setOffset(0);}} title="hồ sơ" targetId="audit-results"/>
        </ResourceState>
      </section>
      {error && <p role="alert" className="error">Không thể xác minh: {error}</p>}
      {checked && <section className="panel" id="audit-verification" aria-live="polite"><h2>Kết quả xác minh chuỗi audit</h2><p className="muted">Mã hồ sơ: {resource.data?.items?.find((item) => item.id === checked.id)?.code || checked.id}</p><Data value={checked.result}/></section>}
    </>
  );
}
