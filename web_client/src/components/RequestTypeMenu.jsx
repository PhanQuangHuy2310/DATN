import { useId, useMemo, useState } from "react";
import { riskLevels, approvalLevels, typeLevels } from "../domain";

/** A compact, searchable selector. Availability is provided by the backend, never inferred here. */
export default function RequestTypeMenu({ options = [], onSelect, disabled = false }) {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("Tất cả");
  const [availability, setAvailability] = useState("all");
  const [levelFilter, setLevelFilter] = useState("all");
  const [expanded, setExpanded] = useState(true);
  const menuId = useId();
  const groups = useMemo(() => ["Tất cả", ...new Set(options.map((item) => item.group || "Khác"))], [options]);
  const counts = useMemo(() => groups.map((name) => [name, name === "Tất cả" ? options.length : options.filter((item) => (item.group || "Khác") === name).length]), [options, groups]);
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("vi-VN");
    return options.filter((item) => {
      const fallback = typeLevels[item.code] || {};
      const appLvl = item.approval_level || fallback.approval_level || 1;
      const riskW = item.risk_weight || fallback.risk_weight || 3;
      return (
        (group === "Tất cả" || (item.group || "Khác") === group) &&
        (availability === "all" || (availability === "available" ? item.available : !item.available)) &&
        (levelFilter === "all" || String(appLvl) === levelFilter || `r${riskW}` === levelFilter) &&
        (!needle || `${item.label || ""} ${item.code || ""} ${item.group || ""} ${item.description || ""}`.toLocaleLowerCase("vi-VN").includes(needle))
      );
    });
  }, [options, query, group, availability, levelFilter]);
  const available = options.filter((item) => item.available).length;

  return (
    <div className="request-menu" aria-label="Chọn loại yêu cầu">
      <div className="request-menu-intro">
        <p className="eyebrow">DANH MỤC YÊU CẦU 5 CẤP</p>
        <h2>Chọn loại yêu cầu</h2>
        <p className="muted">Lọc theo nhóm nghiệp vụ, cấp độ phê duyệt (Cấp 1–5) hoặc tìm tên, sau đó chọn biểu mẫu. Chỉ các loại đã công bố và được cấp quyền mới có thể tạo.</p>
        <div className="request-menu-counts" aria-label="Tổng quan danh mục"><span>{options.length} lựa chọn</span><span>{available} có thể tạo</span><span>Chuẩn phân quyền 5 cấp</span></div>
      </div>
      <div className="request-menu-category-scroll" aria-label="Nhóm nghiệp vụ, cuộn ngang để xem các nhóm khác">
        <div className="request-menu-categories">
          {counts.map(([name, count]) => <button key={name} type="button" disabled={disabled}
            className={`request-menu-category ${group === name ? "is-selected" : ""}`}
            aria-pressed={group === name} onClick={() => { setGroup(name); setExpanded(true); }}>
            <span>{name}</span><small>{count}</small>
          </button>)}
        </div>
      </div>
      <div className="request-menu-tools">
        <label className="request-menu-search"><span className="label-text">Tìm loại yêu cầu</span>
          <input type="search" value={query} onChange={(event) => { setQuery(event.target.value); setExpanded(true); }}
            placeholder="Nghỉ phép, mua sắm, VPN, hợp đồng, tuyển dụng, hotfix…" disabled={disabled}/>
        </label>
        <label className="request-menu-availability"><span className="label-text">Cấp phê duyệt (5 cấp)</span>
          <select value={levelFilter} disabled={disabled} onChange={(event) => { setLevelFilter(event.target.value); setExpanded(true); }}>
            <option value="all">Tất cả 5 cấp duyệt</option>
            <option value="1">Cấp 1 — Duyệt 1 cấp (Quản lý trực tiếp)</option>
            <option value="2">Cấp 2 — Duyệt 2 cấp (Trưởng bộ phận)</option>
            <option value="3">Cấp 3 — Duyệt 3 cấp (Liên phòng ban)</option>
            <option value="4">Cấp 4 — Duyệt 4 cấp (Giám đốc Khối)</option>
            <option value="5">Cấp 5 — Duyệt 5 cấp (Tổng Giám đốc / CTO)</option>
          </select>
        </label>
        <label className="request-menu-availability"><span className="label-text">Trạng thái biểu mẫu</span>
          <select value={availability} disabled={disabled} onChange={(event) => { setAvailability(event.target.value); setExpanded(true); }}>
            <option value="all">Tất cả trạng thái</option><option value="available">Có thể tạo</option><option value="pending">Chưa kích hoạt</option>
          </select>
        </label>
        {(query || group !== "Tất cả" || availability !== "all" || levelFilter !== "all") &&
          <button className="secondary request-menu-clear" type="button" onClick={() => { setQuery(""); setGroup("Tất cả"); setAvailability("all"); setLevelFilter("all"); setExpanded(true); }}>Xóa bộ lọc</button>}
      </div>
      <section className="request-menu-dropdown" aria-label="Danh sách biểu mẫu">
        <button type="button" className="request-menu-dropdown-toggle" disabled={disabled}
          aria-expanded={expanded} aria-controls={menuId} onClick={() => setExpanded((current) => !current)}>
          <span><strong>{group === "Tất cả" ? "Tất cả loại yêu cầu" : group}</strong><small>{filtered.length} kết quả · Nhấn để {expanded ? "thu gọn" : "xổ danh sách"}</small></span>
          <span className={`request-menu-chevron ${expanded ? "is-open" : ""}`} aria-hidden="true">⌄</span>
        </button>
        {expanded && <div id={menuId} className="request-menu-results">
          {filtered.map((item, index) => {
            const fallback = typeLevels[item.code] || {};
            const riskW = item.risk_weight || fallback.risk_weight || 3;
            const appLvl = item.approval_level || fallback.approval_level || 1;
            return (
              <div className={`request-menu-option ${item.available ? "is-live" : "is-pending"}`} key={`${item.group}:${item.code}:${index}`}>
                <div className="request-menu-option-main">
                  <div className="request-menu-option-title"><strong>{item.label}</strong><span className={`request-menu-state ${item.available ? "enabled" : "pending"}`}>{item.available ? "Có thể tạo" : "Chưa kích hoạt"}</span></div>
                  <p>{item.description || "Biểu mẫu theo quy chế được công bố"}</p>
                  <div className="request-menu-option-meta">
                    <span>{item.group || "Khác"}</span>
                    <span>Mẫu {item.lifecycle || "—"}</span>
                    <span title={riskLevels[riskW] || `Trọng số rủi ro ${riskW}`}>Trọng số: Cấp {riskW}/5</span>
                    <span title={approvalLevels[appLvl] || `Phê duyệt ${appLvl} cấp`}>Duyệt: {appLvl}/5 cấp</span>
                    <code>{item.code}</code>
                  </div>
                  {!item.available && <small className="request-menu-warning">{item.disabled_reason || "Chưa công bố quy chế hoặc chưa được cấp quyền"}</small>}
                </div>
                <button type="button" disabled={disabled || !item.available} className={item.available ? "" : "secondary"}
                  onClick={() => onSelect(item)} aria-label={`Chọn biểu mẫu ${item.label}`}>
                  {item.available ? "Chọn biểu mẫu →" : "Chưa khả dụng"}
                </button>
              </div>
            );
          })}
          {filtered.length === 0 && <output className="request-menu-no-results">Không tìm thấy biểu mẫu phù hợp. Hãy thử tên hoặc nhóm khác.</output>}
        </div>}
      </section>
      {options.length === 0 && <output className="request-menu-empty">Hệ thống chưa cấp quyền sử dụng biểu mẫu cho tài khoản này.</output>}
    </div>
  );
}
