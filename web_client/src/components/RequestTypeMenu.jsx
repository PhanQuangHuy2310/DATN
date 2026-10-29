import { useId, useMemo, useState } from "react";

/** A compact, searchable selector. Availability is provided by the backend, never inferred here. */
export default function RequestTypeMenu({ options = [], onSelect, disabled = false }) {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("Tất cả");
  const [availability, setAvailability] = useState("all");
  const [expanded, setExpanded] = useState(true);
  const menuId = useId();
  const groups = useMemo(() => ["Tất cả", ...new Set(options.map((item) => item.group || "Khác"))], [options]);
  const counts = useMemo(() => groups.map((name) => [name, name === "Tất cả" ? options.length : options.filter((item) => (item.group || "Khác") === name).length]), [options, groups]);
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("vi-VN");
    return options.filter((item) =>
      (group === "Tất cả" || (item.group || "Khác") === group) &&
      (availability === "all" || (availability === "available" ? item.available : !item.available)) &&
      (!needle || `${item.label || ""} ${item.code || ""} ${item.group || ""} ${item.description || ""}`.toLocaleLowerCase("vi-VN").includes(needle))
    );
  }, [options, query, group, availability]);
  const available = options.filter((item) => item.available).length;

  return (
    <div className="request-menu" aria-label="Chọn loại yêu cầu">
      <div className="request-menu-intro">
        <p className="eyebrow">DANH MỤC YÊU CẦU</p>
        <h2>Chọn loại yêu cầu</h2>
        <p className="muted">Lọc theo nhóm nghiệp vụ hoặc tìm tên, sau đó mở danh sách và chọn biểu mẫu. Chỉ các loại đã công bố và được cấp quyền mới có thể tạo.</p>
        <div className="request-menu-counts" aria-label="Tổng quan danh mục"><span>{options.length} lựa chọn</span><span>{available} có thể tạo</span></div>
      </div>
      <div className="request-menu-category-scroll" tabIndex={0} aria-label="Lọc theo nhóm nghiệp vụ">
        <div className="request-menu-categories">
          {counts.map(([name, count]) => <button key={name} type="button" disabled={disabled}
            className={`request-menu-category ${group === name ? "is-selected" : ""}`}
            aria-pressed={group === name} onClick={() => { setGroup(name); setExpanded(true); }}>
            <span>{name}</span><small>{count}</small>
          </button>)}
        </div>
      </div>
      <div className="request-menu-tools">
        <label className="request-menu-search">Tìm loại yêu cầu
          <input type="search" value={query} onChange={(event) => { setQuery(event.target.value); setExpanded(true); }}
            placeholder="Nghỉ phép, mua sắm, VPN, hợp đồng…" disabled={disabled}/>
        </label>
        <label className="request-menu-availability">Trạng thái biểu mẫu
          <select value={availability} disabled={disabled} onChange={(event) => { setAvailability(event.target.value); setExpanded(true); }}>
            <option value="all">Tất cả trạng thái</option><option value="available">Có thể tạo</option><option value="pending">Chưa kích hoạt</option>
          </select>
        </label>
        {(query || group !== "Tất cả" || availability !== "all") &&
          <button className="secondary request-menu-clear" type="button" onClick={() => { setQuery(""); setGroup("Tất cả"); setAvailability("all"); setExpanded(true); }}>Xóa bộ lọc</button>}
      </div>
      <section className="request-menu-dropdown" aria-label="Danh sách biểu mẫu">
        <button type="button" className="request-menu-dropdown-toggle" disabled={disabled}
          aria-expanded={expanded} aria-controls={menuId} onClick={() => setExpanded((current) => !current)}>
          <span><strong>{group === "Tất cả" ? "Tất cả loại yêu cầu" : group}</strong><small>{filtered.length} kết quả · Nhấn để {expanded ? "thu gọn" : "xổ danh sách"}</small></span>
          <span className={`request-menu-chevron ${expanded ? "is-open" : ""}`} aria-hidden="true">⌄</span>
        </button>
        {expanded && <div id={menuId} className="request-menu-results">
          {filtered.map((item, index) => <div className={`request-menu-option ${item.available ? "is-live" : "is-pending"}`} key={`${item.group}:${item.code}:${index}`}>
            <div className="request-menu-option-main">
              <div className="request-menu-option-title"><strong>{item.label}</strong><span className={`request-menu-state ${item.available ? "enabled" : "pending"}`}>{item.available ? "Có thể tạo" : "Chưa kích hoạt"}</span></div>
              <p>{item.description || "Biểu mẫu theo quy chế được công bố"}</p>
              <div className="request-menu-option-meta"><span>{item.group || "Khác"}</span><span>Mẫu {item.lifecycle || "—"}</span><code>{item.code}</code></div>
              {!item.available && <small className="request-menu-warning">{item.disabled_reason || "Chưa công bố quy chế hoặc chưa được cấp quyền"}</small>}
            </div>
            <button type="button" disabled={disabled || !item.available} className={item.available ? "" : "secondary"}
              onClick={() => onSelect(item)} aria-label={`Chọn biểu mẫu ${item.label}`}>
              {item.available ? "Chọn biểu mẫu →" : "Chưa khả dụng"}
            </button>
          </div>)}
          {filtered.length === 0 && <div className="request-menu-no-results" role="status">Không tìm thấy biểu mẫu phù hợp. Hãy thử tên hoặc nhóm khác.</div>}
        </div>}
      </section>
      {options.length === 0 && <p role="status">Hệ thống chưa cấp quyền sử dụng biểu mẫu cho tài khoản này.</p>}
    </div>
  );
}
