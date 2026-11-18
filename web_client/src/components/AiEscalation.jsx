import { useEffect, useState } from "react";
import { api } from "../api.js";
import { date } from "../domain.js";
import { command } from "./ui.jsx";

const LIFECYCLE = {
  A: "A (chỉ phê duyệt)",
  B: "B (quản lý duyệt → bộ phận chuyên môn xử lý)",
  C: "C (duyệt nhiều cấp → xử lý → nghiệm thu độc lập)",
};

const ACTION_TEXT = {
  DELEGATE_APPROVALS: "Giao bước duyệt cho người khác",
  REASSIGN_WORK: "Chuyển việc cho người khác",
  POSTPONE_DEADLINE: "Lùi hạn tới sau ngày đi làm lại",
  RESCHEDULE_REQUEST: "Đề nghị đổi ngày nghỉ",
};

const KIND_TEXT = { APPROVAL: "Bước duyệt", EXECUTION: "Việc thực hiện", ACCEPTANCE: "Nghiệm thu" };

export function EscalationBanner({ escalation, requestId, onChanged }) {
  const [note, setNote] = useState("");
  if (!escalation) return null;

  async function markWrong() {
    const reason = window.prompt("Vì sao AI chuyển quy trình nhầm? (AI sẽ nhớ cho người này, loại đơn này)");
    if (!reason || reason.trim().length < 5) return;
    try {
      await api(`/api/v1/requests/${requestId}/ai-feedback/escalation`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      setNote("Đã ghi nhận: lần sau AI không chuyển quy trình cho trường hợp tương tự của người này.");
      onChanged?.();
    } catch (err) {
      setNote(err?.message || "Chỉ người duyệt hồ sơ này mới đánh dấu được.");
    }
  }
  return (
    <section className="ai-escalation" aria-label="AI chuyển quy trình">
      <div className="ai-escalation-head">
        <span className="ai-escalation-badge">AI</span>
        <strong>
          Hồ sơ được chuyển từ quy trình {escalation.from_lifecycle} sang quy trình{" "}
          {escalation.to_lifecycle}
        </strong>
      </div>
      <p className="muted">
        {LIFECYCLE[escalation.to_lifecycle] || escalation.to_lifecycle}
        {escalation.occurred_at ? ` · ${date(escalation.occurred_at)}` : ""}. AI không tự duyệt
        hồ sơ này; người có thẩm quyền xét duyệt thủ công.
      </p>
      {escalation.causes?.length > 0 && (
        <ul className="ai-escalation-causes">
          {escalation.causes.map((c) => (
            <li key={`${c.source}-${c.code}`}>
              <span className="ai-citation-badge applies">
                {c.source === "REGULATION" ? "Quy định" : c.source === "LEARNED" ? "Đã học từ phản hồi" : "Tình huống xấu"}
              </span>{" "}
              <code>{c.code}</code> {c.text}
            </li>
          ))}
        </ul>
      )}
      {requestId && (
        <div className="ai-escalation-learn">
          <button type="button" className="secondary" onClick={markWrong}>
            AI chuyển nhầm
          </button>
          {note && <span className="muted"> {note}</span>}
        </div>
      )}
    </section>
  );
}

function ItemCard({ item, choice, onChange }) {
  const actions = [];
  if (item.candidates.length) {
    actions.push(item.kind === "APPROVAL" ? "DELEGATE_APPROVALS" : "REASSIGN_WORK");
  }
  if (item.postpone_to) actions.push("POSTPONE_DEADLINE");
  return (
    <li className="ai-remedy-item">
      <div className="ai-remedy-item-head">
        <strong>
          {KIND_TEXT[item.kind] || item.kind} · {item.item_code}
        </strong>
        <span className="muted">
          {item.type_name} · hạn {date(item.due_at)} (còn {item.hours_to_due} giờ)
        </span>
      </div>
      {item.title && <p className="muted">{item.title}</p>}
      {item.suggestion && (
        <p className="ai-remedy-suggestion">
          AI gợi ý: <strong>{ACTION_TEXT[item.suggestion.action] || item.suggestion.action}</strong>
          {item.suggestion.why ? ` (${item.suggestion.why})` : ""}
        </p>
      )}
      {actions.length === 0 ? (
        <p className="muted">Không có người phù hợp và không lùi hạn được; đề nghị người gửi đổi ngày nghỉ.</p>
      ) : (
        <div className="ai-remedy-choices">
          <label>
            <input
              type="radio"
              name={`skip-${item.stage_id}`}
              checked={!choice}
              onChange={() => onChange(null)}
            />{" "}
            Không xử lý việc này
          </label>
          {actions.includes("POSTPONE_DEADLINE") && (
            <label>
              <input
                type="radio"
                name={`skip-${item.stage_id}`}
                checked={choice?.action === "POSTPONE_DEADLINE"}
                onChange={() => onChange({ action: "POSTPONE_DEADLINE", stage_id: item.stage_id })}
              />{" "}
              Lùi hạn tới {date(item.postpone_to)}
            </label>
          )}
          {item.candidates.map((c, i) => (
            <label key={c.user_id} className="ai-remedy-candidate">
              <input
                type="radio"
                name={`skip-${item.stage_id}`}
                checked={choice?.candidate_id === c.user_id}
                onChange={() =>
                  onChange({ action: actions[0], stage_id: item.stage_id, candidate_id: c.user_id })
                }
              />{" "}
              <span>
                {i === 0 && <span className="ai-citation-badge applies">AI xếp hạng 1</span>}{" "}
                Giao cho <strong>{c.display_name}</strong>{" "}
                <span className="muted">(điểm {c.score}: {(c.why || []).join("; ")})</span>
              </span>
            </label>
          ))}
        </div>
      )}
    </li>
  );
}

export function RemediationPanel({ requestId, onDone }) {
  const [plan, setPlan] = useState(null);
  const [choices, setChoices] = useState({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let alive = true;
    api(`/api/v1/requests/${requestId}/ai-remediation`, { silent: true })
      .then((data) => {
        if (!alive) return;
        const p = data?.plan || null;
        setPlan(p);
        // Mặc định chọn đúng gợi ý của AI cho từng việc; quản lý vẫn đổi được trước khi xác nhận.
        const init = {};
        for (const item of p?.items || []) {
          const s = item.suggestion?.action;
          if ((s === "DELEGATE_APPROVALS" || s === "REASSIGN_WORK") && item.candidates[0]) {
            init[item.stage_id] = { action: s, stage_id: item.stage_id, candidate_id: item.candidates[0].user_id };
          } else if (s === "POSTPONE_DEADLINE" && item.postpone_to) {
            init[item.stage_id] = { action: s, stage_id: item.stage_id };
          }
        }
        setChoices(init);
      })
      .catch(() => alive && setPlan(null)); // không phải quản lý của hồ sơ: không hiện bảng
    return () => {
      alive = false;
    };
  }, [requestId, version]);

  const open = (plan?.proposals || []).filter((p) => p.state === "PROPOSED");
  if (!plan || !open.length) return null;
  const proposal = open[0];
  const selected = Object.values(choices).filter(Boolean);

  async function confirm() {
    setBusy(true);
    setMessage("");
    try {
      const res = await command(`requests/${requestId}/ai-remediation/confirm`, {
        proposal_id: proposal.id,
        actions: selected,
      });
      setMessage(`Đã thực hiện ${res.applied?.length || 0} thao tác theo đề xuất của AI.`);
      setVersion((v) => v + 1);
      onDone?.();
    } catch (err) {
      setMessage(err?.message || "Không thực hiện được đề xuất.");
    } finally {
      setBusy(false);
    }
  }

  async function dismiss() {
    const reason = window.prompt("Lý do bỏ qua đề xuất của AI (ít nhất 5 ký tự):");
    if (!reason || reason.trim().length < 5) return;
    setBusy(true);
    try {
      await api(`/api/v1/requests/${requestId}/ai-remediation/${proposal.id}/dismiss`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      setVersion((v) => v + 1);
      onDone?.();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="ai-remedy" aria-label="Đề xuất xử lý của AI">
      <h2>AI đề xuất cách xử lý công việc đang dở</h2>
      <p className="muted">
        {proposal.proposal?.message} Người xin nghỉ vắng từ {date(plan.absence.start)} đến trước{" "}
        {date(plan.absence.end)}. Bạn xác nhận, hệ thống thực hiện dưới quyền của bạn và ghi nhật ký
        “AI đề xuất – quản lý xác nhận”.
      </p>
      {plan.items.length === 0 ? (
        <p className="muted">Hiện không còn việc đến hạn cần xử lý.</p>
      ) : (
        <ol className="ai-remedy-items">
          {plan.items.map((item) => (
            <ItemCard
              key={item.stage_id}
              item={item}
              choice={choices[item.stage_id]}
              onChange={(c) => setChoices((prev) => ({ ...prev, [item.stage_id]: c }))}
            />
          ))}
        </ol>
      )}
      <div className="ai-remedy-actions">
        <button type="button" onClick={confirm} disabled={busy || !selected.length}>
          Xác nhận {selected.length} thao tác
        </button>
        <button type="button" className="secondary" onClick={dismiss} disabled={busy}>
          Bỏ qua đề xuất
        </button>
      </div>
      {message && <p role="status">{message}</p>}
    </section>
  );
}
