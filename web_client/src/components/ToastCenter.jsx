import { useEffect, useState } from "react";
import { onToast } from "../api.js";

let nextId = 0;
export default function ToastCenter() {
  const [items, setItems] = useState([]);
  useEffect(() => onToast((event) => {
    const id = ++nextId;
    const item = { id, ...event.detail };
    setItems((existing) => [...existing.slice(-3), item]);
  }), []);
  useEffect(() => {
    if (!items.length) return undefined;
    const ids = items.map(({ id }) => setTimeout(() => {
      setItems((current) => current.filter((item) => item.id !== id));
    }, 4000));
    return () => ids.forEach(clearTimeout);
  }, [items]);
  return (
    <div className="toast-stack" aria-live="polite" aria-relevant="additions">
      {items.map(({ id, message, type }) => (
        <div className={`toast toast-${type}`} key={id}>
          <span className="toast-symbol" aria-hidden="true">{type === "error" ? "!" : "✓"}</span>
          <span>{message}</span>
          <button type="button" aria-label="Đóng thông báo" onClick={() => setItems((a) => a.filter((x) => x.id !== id))}>×</button>
        </div>
      ))}
    </div>
  );
}
