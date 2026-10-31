import { useEffect, useMemo, useRef, useState } from "react";
import { FLOW_DIAGRAMS, relevantDiagrams, resolveLifecycle } from "../flowDiagrams.js";
import "../workflow-diagrams.css";

function ImageViewer({ diagram, onClose }) {
  const [zoom, setZoom] = useState(100);
  const closeRef = useRef(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);
  return (
    <div className="flow-lightbox-backdrop">
      <button
        type="button"
        className="flow-lightbox-dismiss"
        aria-label="Đóng toàn màn hình"
        onClick={onClose}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          background: "transparent",
          border: "none",
          padding: 0,
          margin: 0,
          cursor: "default",
        }}
      />
      <section className="flow-lightbox" role="dialog" aria-modal="true" aria-label={`Xem toàn màn hình: ${diagram.title}`} style={{ position: "relative", zIndex: 1 }}>
        <header className="flow-lightbox-toolbar">
          <div><strong>{diagram.title}</strong><small>Sơ đồ luồng công việc</small></div>
          <div className="flow-viewer-actions">
            <button className="secondary" type="button" aria-label="Thu nhỏ" disabled={zoom <= 60} onClick={() => setZoom((n) => Math.max(60, n - 20))}>−</button>
            <span className="flow-zoom-level" aria-live="polite">{zoom}%</span>
            <button className="secondary" type="button" aria-label="Phóng to" disabled={zoom >= 200} onClick={() => setZoom((n) => Math.min(200, n + 20))}>+</button>
            <a href={diagram.src} download={`EAS-${diagram.id}.webp`} className="flow-download">Tải ảnh</a>
            <button ref={closeRef} className="secondary" type="button" aria-label="Đóng sơ đồ" onClick={onClose}>✕</button>
          </div>
        </header>
        <div className="flow-lightbox-scroll">
          <img src={diagram.src} alt={`Sơ đồ ${diagram.title}`} style={{ width: `${zoom}%` }} />
        </div>
      </section>
    </div>
  );
}

/** Read-only diagrams: no workflow decisions are made in this component. */
export default function WorkflowDiagrams({ request = null, lifecycle = null, embedded = false }) {
  const effectiveLifecycle = resolveLifecycle(request, lifecycle);
  const inContext = Boolean(request || lifecycle);
  const baseList = useMemo(() => inContext ? relevantDiagrams(request, lifecycle) : FLOW_DIAGRAMS, [inContext, request, lifecycle]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("Tất cả");
  const [selectedId, setSelectedId] = useState(null);
  const [fullscreen, setFullscreen] = useState(false);
  const visible = useMemo(() => baseList.filter((diagram) =>
    (category === "Tất cả" || diagram.category === category) &&
    `${diagram.title} ${diagram.description} ${diagram.category}`.toLocaleLowerCase("vi").includes(query.trim().toLocaleLowerCase("vi"))
  ), [baseList, category, query]);
  const preferred = inContext && effectiveLifecycle ? `lifecycle-${effectiveLifecycle.toLowerCase()}` : "create-submit";
  const selected = visible.find((diagram) => diagram.id === selectedId) || visible.find((diagram) => diagram.id === preferred) || visible[0] || null;
  const resetKey = `${request?.id || ""}:${lifecycle || ""}`;
  const [prevResetKey, setPrevResetKey] = useState(resetKey);
  if (prevResetKey !== resetKey) {
    setPrevResetKey(resetKey);
    setSelectedId(null);
    setCategory("Tất cả");
    setQuery("");
  }
  const closeFullscreen = () => setFullscreen(false);
  return (
    <section className={`flow-library ${embedded ? "flow-library-embedded" : ""}`} aria-label="Sơ đồ luồng">
      <div className="flow-library-heading">
        <div>
          <p className="eyebrow">TRỰC QUAN HÓA QUY TRÌNH</p>
          <h2>{inContext ? "Sơ đồ luồng của hồ sơ" : "Thư viện sơ đồ luồng"}</h2>
          <p className="muted">{inContext
            ? `Xem quy trình liên quan${effectiveLifecycle ? ` đến vòng đời ${effectiveLifecycle}` : " đến hồ sơ"} và các tình huống xử lý.`
            : "Xem các bước phê duyệt, thực hiện, nghiệm thu và những luồng xử lý liên quan."}</p>
        </div>
        <span className="flow-count">{baseList.length} sơ đồ</span>
      </div>
      {inContext && !effectiveLifecycle && <p className="flow-info" role="status">Chưa xác định được vòng đời đã công bố cho loại yêu cầu này. Không tự suy đoán sơ đồ phê duyệt; bạn có thể tra cứu thư viện chung.</p>}
      <div className="flow-toolbar">
        <label>
          <span className="visually-hidden">Tìm sơ đồ</span>
          <input type="search" placeholder="Tìm sơ đồ luồng…" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <div className="flow-filters" role="group" aria-label="Lọc sơ đồ">
          {["Tất cả", ...new Set(baseList.map((diagram) => diagram.category))].map((value) => <button key={value} className={category === value ? "flow-filter active" : "flow-filter"} type="button" aria-pressed={category === value} onClick={() => {setCategory(value);setSelectedId(null);}}>{value}</button>)}
        </div>
      </div>
      {visible.length ? (
        <div className="flow-workspace">
          <div className="flow-cards" role="list" aria-label="Danh sách sơ đồ">
            {visible.map((diagram) => (
              <div className="flow-card-item" role="listitem" key={diagram.id}>
                <button type="button" className={`flow-card ${selected?.id === diagram.id ? "selected" : ""}`} aria-pressed={selected?.id === diagram.id} onClick={() => setSelectedId(diagram.id)}>
                  <img src={diagram.src} alt="" loading="lazy" width="362" height="272" />
                  <span className="flow-card-foot"><strong>{diagram.title}</strong><small>{diagram.lifecycle ? `Vòng đời ${diagram.lifecycle}` : diagram.category}</small></span>
                </button>
              </div>
            ))}
          </div>
          {selected && <aside className="flow-preview" aria-label="Xem sơ đồ đang chọn">
            <div className="flow-preview-head"><div><small className="muted">SƠ ĐỒ ĐANG XEM</small><h3>{selected.title}</h3></div><span className="flow-context-label">{selected.lifecycle ? `Vòng đời ${selected.lifecycle}` : selected.category}</span></div>
            <p className="muted">{selected.description}</p>
            <button className="flow-preview-image" type="button" aria-label={`Phóng to ${selected.title}`} onClick={() => setFullscreen(true)}><img src={selected.src} alt={`Sơ đồ ${selected.title}`} /></button>
            <p className="flow-disclaimer">Sơ đồ dùng để tham khảo trình tự xử lý. Trạng thái, số cấp duyệt và quyền thao tác thực tế được xác định từ hồ sơ và quy chế đã công bố.</p>
            <div className="flow-viewer-actions">
              <button type="button" onClick={() => setFullscreen(true)}>⛶ Xem toàn màn hình</button>
              <a className="flow-download" href={selected.src} download={`EAS-${selected.id}.webp`}>↓ Tải ảnh</a>
            </div>
          </aside>}
        </div>
      ) : <div className="flow-empty">Không tìm thấy sơ đồ phù hợp. <button className="link" type="button" onClick={() => {setQuery("");setCategory("Tất cả");}}>Xóa bộ lọc</button></div>}
      {fullscreen && selected && <ImageViewer diagram={selected} onClose={closeFullscreen} />}
    </section>
  );
}
