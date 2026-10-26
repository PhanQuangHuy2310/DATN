import { useMemo, useState } from "react";

/** Distinct business options are grouped; duplicates in the source plan may share one type code. */
export default function RequestTypeMenu({ options = [], onSelect, disabled = false }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => options.filter((item) =>
    `${item.label} ${item.code} ${item.group}`.toLocaleLowerCase("vi-VN")
      .includes(query.trim().toLocaleLowerCase("vi-VN"))), [options, query]);
  const groups = [...new Set(filtered.map((item) => item.group))];
  const available = options.filter((item) => item.available).length;
  return (
    <div className="request-menu" aria-label="Chọn loại yêu cầu">
      <div className="request-menu-intro">
        <p className="eyebrow">DANH MỤC YÊU CẦU</p>
        <h2>Chọn chức năng cần yêu cầu</h2>
        <p className="muted">Chọn nhóm nghiệp vụ, rồi chọn loại đơn. Mã hồ sơ và người xử lý được hệ thống tự xác định; bạn không cần nhập mã hoặc chọn người duyệt.</p>
        <div className="request-menu-counts"><span>{options.length} lựa chọn</span><span>{available} biểu mẫu được phép sử dụng</span></div>
      </div>
      <label className="request-menu-search">Tìm loại yêu cầu
        <input type="search" value={query} onChange={(event) => setQuery(event.target.value)}
          placeholder="Tìm: nghỉ phép, mua sắm, VPN, hợp đồng…" />
      </label>
      {groups.map((group, index) => (
        <details className="request-menu-group" key={group} open={Boolean(query) || index === 0}>
          <summary>{group} <small>{filtered.filter((item) => item.group === group).length} chức năng</small></summary>
          <div className="request-menu-grid">
            {filtered.filter((item) => item.group === group).map((item, itemIndex) => (
              <article className={`request-menu-card ${item.available ? "is-live" : "is-pending"}`} key={`${group}:${item.code}:${itemIndex}`}>
                <div className="request-menu-card-top"><span className="request-menu-template">Mẫu {item.lifecycle}</span>
                  <span className={`request-menu-state ${item.available ? "enabled" : "pending"}`}>
                    {item.available ? "Có thể tạo" : "Chưa kích hoạt"}
                  </span></div>
                <h3>{item.label}</h3>
                <p className="muted">{item.description}</p>
                <div className="request-menu-card-bottom">
                  <small>{item.code}</small>
                  <button type="button" disabled={disabled || !item.available}
                    onClick={() => onSelect(item)} aria-label={`Chọn ${item.label}`}>
                    {item.available ? "Chọn và tạo đơn" : "Chờ công bố"}
                  </button>
                </div>
                {!item.available && <p className="request-menu-warning">{item.disabled_reason || "Quy chế chưa công bố"}</p>}
              </article>
            ))}
          </div>
        </details>
      ))}
      {!groups.length && <p className="empty">Không có loại yêu cầu khớp từ khóa tìm kiếm.</p>}
      {options.length === 0 && <p role="status">Hệ thống chưa cấp quyền sử dụng biểu mẫu cho tài khoản này.</p>}
    </div>
  );
}
