import { useRef, useState } from "react";

export function PasswordField({ label, name, help, ...props }) {
  const [visible, setVisible] = useState(false);
  const id = `eas-password-${name}`;
  return (
    <div className="password-field">
      <label htmlFor={id}>{label}</label>
      <div className="password-control">
        <input id={id} name={name} type={visible ? "text" : "password"} {...props} />
        <button type="button" className="password-toggle" aria-pressed={visible}
          aria-label={visible ? "Ẩn ký tự" : "Hiện ký tự"}
          onClick={() => setVisible((v) => !v)}>
          <span aria-hidden="true">{visible ? "◉" : "◎"}</span> {visible ? "Ẩn" : "Hiện"}
        </button>
      </div>
      {help && <small className="password-hint">{help}</small>}
    </div>
  );
}

export function PageControls({ offset, limit = 20, nextOffset, onPage, onLimit, count = 0, title = "bản ghi", targetId }) {
  const page = Math.floor(offset / limit) + 1;
  const hasNext = nextOffset != null;
  const pageRef = useRef(null);
  function change(next) {
    onPage(next);
    window.requestAnimationFrame(() => {
      const node = targetId ? document.getElementById(targetId) : pageRef.current?.closest("section");
      (node || document.getElementById("main"))?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
  return (
    <nav className="pagination pagination-extended" aria-label={`Phân trang ${title}`} ref={pageRef}>
      <div className="pagination-context"><strong>Trang {page}</strong><span>Hiển thị {count} {title}{count ? ` · Từ ${offset + 1} đến ${offset + count}` : ""}</span></div>
      {onLimit && <label className="page-size">Số dòng / trang <select value={limit} onChange={(e) => { onLimit(Number(e.target.value)); change(0); }}>
        {[10, 20, 50].map((v) => <option key={v} value={v}>{v}</option>)}
      </select></label>}
      <div className="page-buttons">
        <button type="button" className="secondary" disabled={offset === 0} onClick={() => change(0)} aria-label="Trang đầu">«</button>
        <button type="button" className="secondary" disabled={offset === 0} onClick={() => change(Math.max(0, offset - limit))}>← Trước</button>
        <span className="page-number" aria-current="page">{page}</span>
        <button type="button" className="secondary" disabled={!hasNext} onClick={() => change(nextOffset)}>Sau →</button>
      </div>
    </nav>
  );
}

export function useLocalPagination(initial = 10) {
  const [pageSize, setPageSize] = useState(initial);
  const [offset, setOffset] = useState(0);
  return { offset, setOffset, pageSize, setPageSize,
    slice: (items) => items.slice(offset, offset + pageSize),
    nextOffset: (items) => offset + pageSize < items.length ? offset + pageSize : null,
  };
}
