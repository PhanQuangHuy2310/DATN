import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api.js";
import { errorText } from "../domain.js";

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

export default function PlanCatalog() {
  const source = useResource("/api/v1/meta/plan-request-types");
  const deployed = useResource("/api/v1/request-types");
  const [filter,setFilter] = useState("");
  const [catalogMode,setCatalogMode] = useState("business");
  const [group,setGroup] = useState("Tất cả");
  const [releaseFilter,setReleaseFilter] = useState("all");
  const [page,setPage] = useState(0);
  const [selected,setSelected] = useState(null);
  const [notice,setNotice] = useState("");
  const detailRef = useRef(null);
  const listRef = useRef(null);
  function goPage(next) { setPage(next); requestAnimationFrame(() => listRef.current?.scrollIntoView({behavior:"smooth",block:"start"})); }
  const available = useMemo(() => new Map((deployed.data?.items || []).map(x=>[x.code,x])),[deployed.data]);
  const pool = catalogMode === "business"
    ? (source.data?.approval_menu?.types || [])
    : (source.data?.items || []);
  const groups = ["Tất cả", ...new Set(pool.map((x) => x.category))];
  const list = useMemo(() => pool.filter(x => {
    const match = !filter || `${x.name} ${x.code} ${x.category}`.toLowerCase().includes(filter.toLowerCase().trim());
    const db = available.get(x.code);
    const published = !!db?.configured && db.lifecycle === x.lifecycle;
    return match && (group === "Tất cả" || x.category === group) &&
      (releaseFilter === "all" || (releaseFilter === "published" ? published : !published));
  }), [pool, filter, group, releaseFilter, available]);
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
      <div><p className="eyebrow">QUẢN TRỊ QUY CHẾ / PLAN.DOCX</p>
        <h1>Danh mục loại yêu cầu</h1>
        <p className="muted">Bảng danh mục lựa chọn của nhân viên và bản danh mục mã gốc trong plan.docx. Phải có quy chế đã công bố và role hợp lệ mới tạo đơn được.</p>
      </div>
    </header>
    <section className="panel plan-catalog-overview">
      <div className="plan-stat"><strong>{pool.length}</strong><span>Mã loại {catalogMode === "business" ? "theo bảng chọn" : "từ plan.docx"}</span></div>
      <div className="plan-stat"><strong>3</strong><span>Mẫu A / B / C</span></div>
      <div className="plan-stat"><strong>{(deployed.data?.items||[]).filter(x=>x.configured && source.data?.items?.some(p=>p.code===x.code)).length}</strong><span>Có release được công bố</span></div>
      <p className="muted plan-note">Có 20 lựa chọn hiển thị theo bốn nhóm, nhưng hai loại nghỉ dài ngày và laptop được sử dụng lại ở nhóm khác; tổng cộng 18 mã khác nhau. Đơn chỉ được gửi khi có release và quyền tương ứng.</p>
    </section>
    <section className="panel" ref={listRef}>
      <div className="actions" aria-label="Chọn bộ danh mục">
        <button type="button" className={catalogMode === "business" ? "" : "secondary"}
          onClick={()=>{setCatalogMode("business");setGroup("Tất cả");setReleaseFilter("all");setPage(0);setSelected(null);}}>Bảng chọn yêu cầu của nhân viên (20 mục)</button>
        <button type="button" className={catalogMode === "plan" ? "" : "secondary"}
          onClick={()=>{setCatalogMode("plan");setGroup("Tất cả");setReleaseFilter("all");setPage(0);setSelected(null);}}>18 mã kế hoạch mở rộng</button>
      </div>
      <div className="plan-filter-toolbar">
        <label>Tìm theo tên hoặc mã
          <input type="search" value={filter} onChange={e=>{setFilter(e.target.value);setPage(0);}} placeholder="Ví dụ: VPN, nghỉ phép, SAAS…" />
        </label>
        <label>Trạng thái công bố
          <select value={releaseFilter} onChange={e=>{setReleaseFilter(e.target.value);setPage(0);}}>
            <option value="all">Tất cả trạng thái</option><option value="published">Đã có release</option><option value="pending">Chưa có release phù hợp</option>
          </select>
        </label>
      </div>
      <div className="plan-category-scroll" tabIndex={0} aria-label="Lọc theo nhóm yêu cầu">
        <div className="plan-category-row">{groups.map(name=><button type="button" key={name} className={`plan-category-pill ${group===name ? "selected" : ""}`}
          aria-pressed={group===name} onClick={()=>{setGroup(name);setPage(0);}}>{name}<small>{name==="Tất cả" ? pool.length : pool.filter(item=>item.category===name).length}</small></button>)}</div>
      </div>
      <div className="plan-list-count" role="status">{list.length} loại phù hợp bộ lọc</div>
      {source.loading && <p role="status">Đang nạp danh mục từ plan.docx…</p>}
      {source.error && <p className="error" role="alert">{source.error}</p>}
      {deployed.error && <p className="muted">Chưa lấy được trạng thái database: {deployed.error}</p>}
      <div className="plan-type-list">
        {pageItems.map((item,index)=>{
          const db=available.get(item.code);
          const live=!!db?.configured && db.lifecycle===item.lifecycle;
          return <div className="plan-type-row" key={`${item.code}:${item.category}:${index}`}>
            <div className="plan-type-identity"><strong>{item.name}</strong><span>{item.category} · {item.code}</span></div>
            <div className="plan-type-meta"><span className="plan-template">Mẫu {item.lifecycle}</span><small>{item.sla_hours ? `SLA ${item.sla_hours} giờ` : "SLA theo quy chế"}</small></div>
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
      <div className="section-head"><div><p className="eyebrow">CHI TIẾT ĐẶC TẢ</p><h2>{selected.name}</h2><p className="muted">{selected.code} · Mẫu {selected.lifecycle}{selected.sla_hours ? ` · SLA ${selected.sla_hours} giờ` : " · SLA theo quy chế"}</p></div><button className="secondary" onClick={()=>setSelected(null)}>Đóng</button></div>
      <div className="plan-detail-grid">
        <div><h3>Luồng phê duyệt</h3><p>{selected.approval_route || "Được xác định từ bản quy chế đã công bố"}</p></div>
        <div><h3>Người thực hiện</h3><p>{selected.executor || (selected.lifecycle === "A" ? "Không cần" : "Được gán khi gửi")}</p></div>
        <div><h3>Nghiệm thu</h3><p>{selected.acceptor || (selected.lifecycle !== "C" ? "Không bắt buộc" : "Theo bản quy chế")}</p></div>
        <div><h3>AI hỗ trợ</h3><p>{selected.ai_hook || "Chỉ gợi ý, không tự kích hoạt duyệt"}</p></div>
      </div>
      <h3>Trường bắt buộc</h3>
      <div className="plan-fields">{(selected.required_fields || selected.form_schema?.required?.filter(f=>f!=="title") || []).map(f=><span key={f}>{selected.field_labels[f] || f} <small>({f})</small></span>)}</div>
      {!!selected.activation_warnings?.length && <div className="plan-warnings" role="note"><strong>Yêu cầu rà soát trước khi kích hoạt</strong>{selected.activation_warnings.map(w=><p key={w}>{w}</p>)}</div>}
      <p className="muted">Template thiết kế chỉ phục vụ lập bản nháp chính sách. Không tự động cho phép AI phê duyệt hay bỏ qua kiểm tra quyền và nghiệm thu.</p>
      <button onClick={copySchema}>Sao chép JSON Schema</button>
      {notice && <p role="status" className="success">{notice}</p>}
      <details><summary>JSON Schema để cấu hình biểu mẫu</summary><pre className="plan-code">{JSON.stringify(selected.form_schema,null,2)}</pre></details>
    </section>}
  </>;
}
