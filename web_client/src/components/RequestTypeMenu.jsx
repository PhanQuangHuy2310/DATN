import { useId, useMemo, useState } from "react";
import { riskLevels, approvalLevels, typeLevels } from "../domain";

const GROUP_ICONS = {
  "Nghỉ phép & Chấm công": "🗓️",
  "Nhân sự & Đào tạo": "👥",
  "Tạm ứng & Thanh toán": "💳",
  "Ngân sách & Thuế": "📊",
  "Mua sắm & Tài sản": "📦",
  "Phòng họp & Xe công vụ": "🏢",
  "Cơ sở vật chất & An ninh": "🛡️",
  "Tài khoản & Phân quyền CNTT": "🔐",
  "Hạ tầng & Vận hành kỹ thuật": "⚙️",
  "Hợp đồng & Pháp chế": "⚖️",
  "Kinh doanh & Marketing": "📈",
  "Khác / Linh hoạt": "✨",
};

function resolveGroupIcon(name = "") {
  if (GROUP_ICONS[name]) return GROUP_ICONS[name];
  const lower = name.toLocaleLowerCase("vi-VN");
  if (lower.includes("nghỉ") || lower.includes("chấm công")) return "🗓️";
  if (lower.includes("nhân sự") || lower.includes("tuyển")) return "👥";
  if (lower.includes("tài chính") || lower.includes("thanh toán") || lower.includes("tạm ứng")) return "💳";
  if (lower.includes("ngân sách") || lower.includes("thuế")) return "📊";
  if (lower.includes("mua sắm") || lower.includes("tài sản") || lower.includes("thiết bị")) return "📦";
  if (lower.includes("phòng") || lower.includes("xe")) return "🏢";
  if (lower.includes("vật chất") || lower.includes("an ninh")) return "🛡️";
  if (lower.includes("truy cập") || lower.includes("phân quyền") || lower.includes("cntt") || lower.includes("it")) return "🔐";
  if (lower.includes("hạ tầng") || lower.includes("máy chủ") || lower.includes("vận hành")) return "⚙️";
  if (lower.includes("hợp đồng") || lower.includes("pháp")) return "⚖️";
  if (lower.includes("kinh doanh") || lower.includes("marketing")) return "📈";
  return "📋";
}

/**
 * Two steps (docs/PHAN_LOAI_YEU_CAU.md): pick a large group, then a small request type.
 * Search covers every type regardless of group. Availability is provided by the backend.
 */
export default function RequestTypeMenu({
  options = [],
  groups: groupInfo = [],
  onSelect,
  disabled = false,
}) {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("Tất cả");
  const [availability, setAvailability] = useState("all");
  const [levelFilter, setLevelFilter] = useState("all");
  const [expanded, setExpanded] = useState(true);
  const menuId = useId();

  const groups = useMemo(
    () => ["Tất cả", ...new Set(options.map((item) => item.group || "Khác"))],
    [options],
  );
  const counts = useMemo(
    () =>
      groups.map((name) => [
        name,
        name === "Tất cả"
          ? options.length
          : options.filter((item) => (item.group || "Khác") === name).length,
      ]),
    [options, groups],
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("vi-VN");
    return options.filter((item) => {
      const fallback = typeLevels[item.code] || {};
      const appLvl = item.approval_level || fallback.approval_level || 1;
      const riskW = item.risk_weight || fallback.risk_weight || 3;
      return (
        (group === "Tất cả" || (item.group || "Khác") === group) &&
        (availability === "all" ||
          (availability === "available" ? item.available : !item.available)) &&
        (levelFilter === "all" ||
          String(appLvl) === levelFilter ||
          `r${riskW}` === levelFilter) &&
        (!needle ||
          `${item.label || ""} ${item.name || ""} ${item.code || ""} ${item.group || ""} ${item.description || ""}`
            .toLocaleLowerCase("vi-VN")
            .includes(needle))
      );
    });
  }, [options, query, group, availability, levelFilter]);

  const available = options.filter((item) => item.available).length;
  const describe = (name) => groupInfo.find((g) => g.label === name)?.description || "";
  const showGroupCards =
    group === "Tất cả" &&
    !query.trim() &&
    availability === "all" &&
    levelFilter === "all";

  return (
    <div className="request-menu" aria-label="Chọn loại yêu cầu">
      <div className="request-menu-intro">
        <p className="eyebrow">BƯỚC 1 / DANH MỤC BIỂU MẪU</p>
        <h2>Chọn nhóm nghiệp vụ hoặc tìm biểu mẫu cần tạo</h2>
        <p className="muted">
          Chọn nhóm nghiệp vụ bên dưới hoặc gõ từ khóa để tìm nhanh biểu mẫu phù hợp.
          Hệ thống tự động áp dụng đúng tuyến phê duyệt theo quy chế hiện hành.
        </p>
        <div className="request-menu-counts" aria-label="Tổng quan danh mục">
          <span>{options.length} biểu mẫu nghiệp vụ</span>
          <span>{available} biểu mẫu sẵn sàng tạo</span>
        </div>
      </div>

      <div className="request-menu-tools">
        <label className="request-menu-search">
          <span className="label-text">Tìm nhanh biểu mẫu</span>
          <input
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setExpanded(true);
            }}
            placeholder="Nghỉ phép, công tác, phòng họp, xe công vụ, thanh toán, thiết bị…"
            disabled={disabled}
          />
        </label>
        <label className="request-menu-availability">
          <span className="label-text">Số cấp phê duyệt</span>
          <select
            value={levelFilter}
            disabled={disabled}
            onChange={(event) => {
              setLevelFilter(event.target.value);
              setExpanded(true);
            }}
          >
            <option value="all">Tất cả cấp phê duyệt</option>
            <option value="1">Duyệt 1 cấp (Quản lý trực tiếp)</option>
            <option value="2">Duyệt 2 cấp (Trưởng bộ phận)</option>
            <option value="3">Duyệt 3 cấp (Liên phòng ban)</option>
            <option value="4">Duyệt 4 cấp (Giám đốc Khối)</option>
            <option value="5">Duyệt 5 cấp (Tổng Giám đốc / CTO)</option>
          </select>
        </label>
        <label className="request-menu-availability">
          <span className="label-text">Trạng thái biểu mẫu</span>
          <select
            value={availability}
            disabled={disabled}
            onChange={(event) => {
              setAvailability(event.target.value);
              setExpanded(true);
            }}
          >
            <option value="all">Tất cả trạng thái</option>
            <option value="available">Sẵn sàng tạo</option>
            <option value="pending">Chưa kích hoạt</option>
          </select>
        </label>
        {(query ||
          group !== "Tất cả" ||
          availability !== "all" ||
          levelFilter !== "all") && (
          <button
            className="secondary request-menu-clear"
            type="button"
            onClick={() => {
              setQuery("");
              setGroup("Tất cả");
              setAvailability("all");
              setLevelFilter("all");
              setExpanded(true);
            }}
          >
            Đặt lại bộ lọc
          </button>
        )}
      </div>

      {showGroupCards ? (
        <div className="request-group-grid" aria-label="Nhóm yêu cầu">
          {counts
            .filter(([name]) => name !== "Tất cả")
            .map(([name, count]) => (
              <button
                key={name}
                type="button"
                disabled={disabled}
                className="request-group-card"
                onClick={() => {
                  setGroup(name);
                  setExpanded(true);
                }}
              >
                <div className="request-group-card-head">
                  <span className="request-group-icon" aria-hidden="true">
                    {resolveGroupIcon(name)}
                  </span>
                  <small>{count} biểu mẫu</small>
                </div>
                <strong>{name}</strong>
                <span>{describe(name) || "Danh mục biểu mẫu nghiệp vụ"}</span>
              </button>
            ))}
        </div>
      ) : (
        <div className="request-group-back">
          <button
            type="button"
            className="secondary"
            disabled={disabled}
            onClick={() => {
              setGroup("Tất cả");
              setQuery("");
              setAvailability("all");
              setLevelFilter("all");
            }}
          >
            ← Tất cả nhóm nghiệp vụ
          </button>
          {group !== "Tất cả" && (
            <span>
              <strong>{group}</strong>
              {describe(group) ? ` — ${describe(group)}` : ""}
            </span>
          )}
        </div>
      )}

      {!showGroupCards && (
        <section className="request-menu-dropdown" aria-label="Danh sách biểu mẫu">
          <button
            type="button"
            className="request-menu-dropdown-toggle"
            disabled={disabled}
            aria-expanded={expanded}
            aria-controls={menuId}
            onClick={() => setExpanded((current) => !current)}
          >
            <span>
              <strong>
                {group === "Tất cả" ? "Kết quả tìm kiếm biểu mẫu" : group}
              </strong>
              <small>
                {filtered.length} biểu mẫu phù hợp · Nhấn để{" "}
                {expanded ? "thu gọn" : "mở danh sách"}
              </small>
            </span>
            <span
              className={`request-menu-chevron ${expanded ? "is-open" : ""}`}
              aria-hidden="true"
            >
              ⌄
            </span>
          </button>
          {expanded && (
            <div id={menuId} className="request-menu-results">
              {filtered.map((item, index) => {
                const fallback = typeLevels[item.code] || {};
                const riskW = item.risk_weight || fallback.risk_weight || 3;
                const appLvl = item.approval_level || fallback.approval_level || 1;
                return (
                  <div
                    className={`request-menu-option ${item.available ? "is-live" : "is-pending"}`}
                    key={`${item.group}:${item.menu_code || item.code}:${index}`}
                  >
                    <div className="request-menu-option-main">
                      <div className="request-menu-option-title">
                        <strong>{item.label}</strong>
                        {item.isBlocked ? (
                          <span className="request-menu-state is-blocked">
                            ⚠ Tạm ngưng (API tắt)
                          </span>
                        ) : (
                          <span
                            className={`request-menu-state ${item.available ? "enabled" : "pending"}`}
                          >
                            {item.available ? "Sẵn sàng tạo" : "Chưa kích hoạt"}
                          </span>
                        )}
                      </div>
                      <p>{item.description || "Biểu mẫu theo quy chế phê duyệt hiện hành"}</p>
                      <div className="request-menu-option-meta">
                        <span>{item.group || "Khác"}</span>
                        <span>Quy trình {item.lifecycle || "A"}</span>
                        <span title={riskLevels[riskW] || `Trọng số rủi ro ${riskW}`}>
                          Rủi ro cấp {riskW}/5
                        </span>
                        <span title={approvalLevels[appLvl] || `Phê duyệt ${appLvl} cấp`}>
                          Duyệt {appLvl} cấp
                        </span>
                      </div>
                      {!item.available && (
                        <small className="request-menu-warning">
                          {item.disabled_reason ||
                            "Chưa công bố quy chế hoặc tài khoản chưa được phân quyền"}
                        </small>
                      )}
                    </div>
                    <button
                      type="button"
                      disabled={disabled || !item.available || item.isBlocked}
                      className={item.available && !item.isBlocked ? "" : "secondary"}
                      onClick={() => onSelect(item)}
                      aria-label={`Chọn biểu mẫu ${item.label}`}
                      title={
                        item.isBlocked
                          ? item.blockedNotice || "Tạm ngưng do kết nối hệ thống liên quan bị tắt"
                          : undefined
                      }
                    >
                      {item.isBlocked
                        ? "Tạm ngưng (API tắt)"
                        : item.available
                          ? "Chọn biểu mẫu →"
                          : "Chưa khả dụng"}
                    </button>
                  </div>
                );
              })}
              {filtered.length === 0 && (
                <output className="request-menu-no-results">
                  Không tìm thấy biểu mẫu phù hợp. Vui lòng thử từ khóa hoặc bộ lọc khác.
                </output>
              )}
            </div>
          )}
        </section>
      )}

      <section
        className="client-other-request"
        aria-label="Yêu cầu ngoài danh mục mẫu có sẵn"
      >
        <div>
          <strong>Tạo yêu cầu khác</strong>
          <p className="muted">
            Dành cho đề xuất đặc thù ngoài 12 nhóm tiêu chuẩn khi đã được Quản trị quy chế
            mở biểu mẫu linh hoạt.
          </p>
        </div>
        {options.some(
          (item) =>
            ["OTHER", "OTHER_REQUEST", "CUSTOM_REQUEST", "GENERAL_REQUEST"].includes(
              item.code,
            ) && item.available,
        ) ? (
          <button
            type="button"
            onClick={() =>
              onSelect(
                options.find(
                  (item) =>
                    [
                      "OTHER",
                      "OTHER_REQUEST",
                      "CUSTOM_REQUEST",
                      "GENERAL_REQUEST",
                    ].includes(item.code) && item.available,
                ),
              )
            }
          >
            Tạo yêu cầu khác →
          </button>
        ) : (
          <small className="client-other-unavailable">
            Chưa có mẫu linh hoạt được công bố. Hãy liên hệ quản trị để tạo và công bố loại
            yêu cầu này.
          </small>
        )}
      </section>

      {options.length === 0 && (
        <output className="request-menu-empty">
          Tài khoản của bạn hiện chưa được phân quyền tạo biểu mẫu yêu cầu.
        </output>
      )}
    </div>
  );
}
