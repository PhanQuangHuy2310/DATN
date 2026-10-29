import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api.js";
import { errorText, riskLevels, approvalLevels, typeLevels } from "../domain.js";

const perPage = 8;

const useResource = (url) => {
  const [state, setState] = useState({loading: true, data: null, error: ""});
  useEffect(() => {
    let alive = true;
    api(url).then(data => alive && setState({loading:false, data, error:""}))
      .catch(err => alive && setState({loading:false,data:null,error:errorText(err)}));
    return () => { alive = false; };
  }, [url]);
  return state;
};

function getCatalogModeLabel(mode) {
  if (mode === "business") return "theo bảng chọn";
  if (mode === "enterprise") return "Quản trị 5 Cấp";
  return "từ plan.docx";
}

export default function PlanCatalog() {
  const source = useResource("/api/v1/meta/plan-request-types");
  const deployed = useResource("/api/v1/request-types");
  const [filter,setFilter] = useState("");
  const [catalogMode,setCatalogMode] = useState("business");
  const [group,setGroup] = useState("Tất cả");
  const [releaseFilter,setReleaseFilter] = useState("all");
  const [levelFilter,setLevelFilter] = useState("all");
  const [page,setPage] = useState(0);
  const [selected,setSelected] = useState(null);
  const [notice,setNotice] = useState("");
  const detailRef = useRef(null);
  const listRef = useRef(null);
  function goPage(next) { setPage(next); requestAnimationFrame(() => listRef.current?.scrollIntoView({behavior:"smooth",block:"start"})); }
  const available = useMemo(() => new Map((deployed.data?.items || []).map(x=>[x.code,x])),[deployed.data]);
  const pool = useMemo(() => {
    if (catalogMode === "business") return source.data?.approval_menu?.types || [];
    if (catalogMode === "enterprise") return source.data?.enterprise_items || [];
    return source.data?.items || [];
  }, [catalogMode, source.data]);
  const groups = useMemo(() => ["Tất cả", ...new Set(pool.map((x) => x.category))], [pool]);
  const list = useMemo(() => pool.filter(x => {
    const match = !filter || `${x.name} ${x.code} ${x.category}`.toLowerCase().includes(filter.toLowerCase().trim());
    const db = available.get(x.code);
    const published = !!db?.configured && db.lifecycle === x.lifecycle;
    const appLvl = x.approval_level || db?.approval_level || typeLevels[x.code]?.approval_level || 1;
    return match && (group === "Tất cả" || x.category === group) &&
      (releaseFilter === "all" || (releaseFilter === "published" ? published : !published)) &&
      (levelFilter === "all" || String(appLvl) === levelFilter);
  }), [pool, filter, group, releaseFilter, levelFilter, available]);
  const pageItems = list.slice(page*perPage,(page+1)*perPage);
  function open(type) {
    setSelected(type);
    setNotice("");
    requestAnimationFrame(()=>detailRef.current?.scrollIntoView({behavior:"smooth",block:"start"}));
  }
  async function copySchema() {
    try {
      await navigator.clipboard.writeText(JSON.stringify(selected.form_schema,null,2));
      setNotice("Đã sao chép JSON Schema. Dán vào bản nháp Policy và cấu hình đủ approver/executor/acceptor trước khi công bố.");
    } catch {
      setNotice("Không có quyền sao chép tự động. Chọn và sao chép JSON bên dưới.");
    }
  }
  return <>
    <header className="page-heading">
      <div><p className="eyebrow">QUẢN TRỊ QUY CHẾ / PHÂN CẤP 5 TẦNG</p>
        <h1>Danh mục loại yêu cầu</h1>
        <p className="muted">Bảng danh mục 53 loại yêu cầu toàn doanh nghiệp theo mô hình phân quyền 5 cấp (Cấp 1–5). Phải có quy chế đã công bố và role hợp lệ mới tạo đơn được.</p>
      </div>
    </header>
    <section className="panel plan-catalog-overview">
      <div className="plan-stat"><strong>{pool.length}</strong><span>Mã loại {getCatalogModeLabel(catalogMode)}</span></div>
      <div className="plan-stat"><strong>5 Cấp</strong><span>Phân tầng Rủi ro & Phê duyệt</span></div>
      <div className="plan-stat"><strong>{(deployed.data?.items||[]).filter(x=>x.configured).length}</strong><span>Tổng mã có release hoạt động</span></div>
      <p className="muted plan-note">Hệ thống vận hành đầy đủ 53 loại yêu cầu (10 Core + 18 Menu + 13 Plan + 12 Enterprise 5 Cấp) trải đều trên 5 tầng trọng số rủi ro và 1–5 cấp phê duyệt tuần tự.</p>
    </section>
    <section className="panel" ref={listRef}>
      <div className="actions" aria-label="Chọn bộ danh mục">
        <button type="button" className={catalogMode === "business" ? "" : "secondary"}
          onClick={()=>{setCatalogMode("business");setGroup("Tất cả");setReleaseFilter("all");setLevelFilter("all");setPage(0);setSelected(null);}}>Bảng chọn yêu cầu của nhân viên (18 mã)</button>
        <button type="button" className={catalogMode === "plan" ? "" : "secondary"}
          onClick={()=>{setCatalogMode("plan");setGroup("Tất cả");setReleaseFilter("all");setLevelFilter("all");setPage(0);setSelected(null);}}>18 mã kế hoạch mở rộng</button>
        <button type="button" className={catalogMode === "enterprise" ? "" : "secondary"}
          onClick={()=>{setCatalogMode("enterprise");setGroup("Tất cả");setReleaseFilter("all");setLevelFilter("all");setPage(0);setSelected(null);}}>12 mã Quản trị Doanh nghiệp 5 Cấp</button>
      </div>
      <div className="plan-filter-toolbar">
        <label><span className="label-text">Tìm theo tên hoặc mã</span>
          <input type="search" value={filter} onChange={e=>{setFilter(e.target.value);setPage(0);}} placeholder="Ví dụ: VPN, nghỉ phép, SAAS, tuyển dụng, hotfix…" />
        </label>
        <label><span className="label-text">Cấp phê duyệt (5 cấp)</span>
          <select value={levelFilter} onChange={e=>{setLevelFilter(e.target.value);setPage(0);}}>
            <option value="all">Tất cả 5 cấp</option>
            <option value="1">Cấp 1 (Duyệt 1 cấp)</option>
            <option value="2">Cấp 2 (Duyệt 2 cấp)</option>
            <option value="3">Cấp 3 (Duyệt 3 cấp)</option>
            <option value="4">Cấp 4 (Duyệt 4 cấp)</option>
            <option value="5">Cấp 5 (Duyệt 5 cấp)</option>
          </select>
        </label>
        <label><span className="label-text">Trạng thái công bố</span>
          <select value={releaseFilter} onChange={e=>{setReleaseFilter(e.target.value);setPage(0);}}>
            <option value="all">Tất cả trạng thái</option><option value="published">Đã có release</option><option value="pending">Chưa có release phù hợp</option>
          </select>
        </label>
      </div>
      <div className="plan-category-scroll" aria-label="Lọc nhóm yêu cầu, cuộn ngang để xem các nhóm khác">
        <div className="plan-category-row">{groups.map(name=><button type="button" key={name} className={`plan-category-pill ${group===name ? "selected" : ""}`}
          aria-pressed={group===name} onClick={()=>{setGroup(name);setPage(0);}}>{name}<small>{name==="Tất cả" ? pool.length : pool.filter(item=>item.category===name).length}</small></button>)}</div>
      </div>
      <output className="plan-list-count">{list.length} loại phù hợp bộ lọc</output>
      {source.loading && <output className="plan-status">Đang nạp danh mục…</output>}
      {source.error && <p className="error" role="alert">{source.error}</p>}
      {deployed.error && <p className="muted">Chưa lấy được trạng thái database: {deployed.error}</p>}
      <div className="plan-type-list">
        {pageItems.map((item,index)=>{
          const db=available.get(item.code);
          const live=!!db?.configured && db.lifecycle===item.lifecycle;
          const riskW = item.risk_weight || db?.risk_weight || typeLevels[item.code]?.risk_weight || 3;
          const appLvl = item.approval_level || db?.approval_level || typeLevels[item.code]?.approval_level || 1;
          return <div className="plan-type-row" key={`${item.code}:${item.category}:${index}`}>
            <div className="plan-type-identity"><strong>{item.name}</strong><span>{item.category} · {item.code}</span></div>
            <div className="plan-type-meta">
              <span className="plan-template">Mẫu {item.lifecycle}</span>
              <small>Trọng số Cấp {riskW}/5 · Duyệt {appLvl}/5 cấp</small>
            </div>
            <span className={live?'plan-live':'plan-pending'}>{live?'Đã có release':db?'Chưa có release':'Chưa đăng ký DB'}</span>
            <button type="button" className="secondary" onClick={()=>open(item)}>Xem đặc tả →</button>
          </div>;
        })}
      </div>
      {!source.loading && !list.length && <p className="empty">Không tìm thấy loại yêu cầu phù hợp.</p>}
      <div className="plan-paginator">
        <span>Hiển thị {list.length? page*perPage+1:0}–{Math.min((page+1)*perPage,list.length)} / {list.length}</span>
        <button type="button" className="secondary" disabled={page===0} onClick={()=>goPage(Math.max(0,page-1))}>Trang trước</button>
        <button type="button" className="secondary" disabled={(page+1)*perPage>=list.length} onClick={()=>goPage(page+1)}>Trang tiếp</button>
      </div>
    </section>
    {selected && <section className="panel plan-detail" ref={detailRef} id="plan-type-details">
      <div className="section-head">
        <div>
          <p className="eyebrow">CHI TIẾT ĐẶC TẢ 5 CẤP</p>
          <h2>{selected.name}</h2>
          <p className="muted">
            {selected.code} · Mẫu {selected.lifecycle}
            {` · ${riskLevels[selected.risk_weight || typeLevels[selected.code]?.risk_weight || 3]}`}
            {` · ${approvalLevels[selected.approval_level || typeLevels[selected.code]?.approval_level || 1]}`}
            {selected.sla_hours ? ` · SLA ${selected.sla_hours} giờ` : " · SLA theo quy chế"}
          </p>
        </div>
        <button type="button" className="secondary" onClick={()=>setSelected(null)}>Đóng</button>
      </div>
      <div className="plan-detail-grid">
        <div><h3>Luồng phê duyệt (1–5 cấp)</h3><p>{selected.approval_route || "Được xác định từ bản quy chế đã công bố"}</p></div>
        <div><h3>Người thực hiện</h3><p>{selected.executor || (selected.lifecycle === "A" ? "Không cần" : "Được gán khi gửi")}</p></div>
        <div><h3>Nghiệm thu</h3><p>{selected.acceptor || (selected.lifecycle !== "C" ? "Không bắt buộc" : "Theo bản quy chế")}</p></div>
        <div><h3>AI hỗ trợ</h3><p>{selected.ai_hook || "Chỉ gợi ý, không tự kích hoạt duyệt"}</p></div>
      </div>
      <h3>Trường bắt buộc</h3>
      <div className="plan-fields">{(selected.required_fields || selected.form_schema?.required?.filter(f=>f!=="title") || []).map(f=><span key={f}>{selected.field_labels?.[f] || f} <small>({f})</small></span>)}</div>
      {!!selected.activation_warnings?.length && <div className="plan-warnings" role="note"><strong>Yêu cầu rà soát trước khi kích hoạt</strong>{selected.activation_warnings.map(w=><p key={w}>{w}</p>)}</div>}
      <p className="muted">Template thiết kế chỉ phục vụ lập bản nháp chính sách. Không tự động cho phép AI phê duyệt hay bỏ qua kiểm tra quyền và nghiệm thu.</p>
      <button type="button" onClick={copySchema}>Sao chép JSON Schema</button>
      {notice && <output className="success">{notice}</output>}
      <details><summary>JSON Schema để cấu hình biểu mẫu</summary><pre className="plan-code">{JSON.stringify(selected.form_schema,null,2)}</pre></details>
    </section>}
  </>;
}
