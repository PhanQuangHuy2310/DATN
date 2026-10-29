import { useState } from "react";
import { errorText } from "../domain.js";
import { useResource } from "./ui.jsx";

/** Editor-only helper: server still validates binding UUIDs and scoped role grants. */
export default function PolicyBindings({ release, jsonText, onChange }) {
  const candidates = useResource(`/api/v1/config-releases/actor-options?type_code=${encodeURIComponent(release.type_code)}`);
  const [deptId, setDeptId] = useState("");
  const [slotName, setSlotName] = useState("");
  const [userId, setUserId] = useState("");
  const [message, setMessage] = useState("");
  const departments = candidates.data?.departments || [];
  const currentDept = departments.find((d) => d.id === deptId) || departments[0];
  const route = release.route_rules || {};
  const requested = [];
  for (const rule of route.rules || []) for (const slot of rule.approvers || []) {
    if (slot !== "DIRECT_MANAGER" && !requested.some((v) => v.slot === slot)) requested.push({slot, role:"APPROVER"});
  }
  if (route.executor && route.executor !== "DIRECT_MANAGER") requested.push({slot:route.executor,role:"EXECUTOR"});
  if (route.acceptor && !["DIRECT_MANAGER", "REQUESTER"].includes(route.acceptor)) requested.push({slot:route.acceptor,role:"ACCEPTOR"});
  const chosenSlot = requested.find((x) => x.slot === slotName) || requested[0];
  const validUsers = (currentDept?.candidates || []).filter((u) => chosenSlot?.role && u.roles.includes(chosenSlot.role));
  const chosenUser = validUsers.find((u) => u.id === userId) || validUsers[0];
  const [prevReleaseId, setPrevReleaseId] = useState(release.id);
  if (release.id !== prevReleaseId) {
    setPrevReleaseId(release.id);
    setDeptId("");
    setSlotName("");
    setUserId("");
    setMessage("");
  }

  function updateBinding(assign) {
    if (!currentDept) return;
    try {
      const doc = JSON.parse(jsonText);
      if (!doc || typeof doc !== "object" || Array.isArray(doc)) throw new Error("actor_bindings phải là object.");
      doc.schema_version = 1;
      doc.departments = (doc.departments && typeof doc.departments === "object" && !Array.isArray(doc.departments)) ? doc.departments : {};
      const original = doc.departments[currentDept.id] || {};
      doc.departments[currentDept.id] = {...original};
      if (assign) {
        if (!chosenSlot || !chosenUser) throw new Error("Chưa có người được cấp role tương ứng ở phòng ban này.");
        doc.departments[currentDept.id][chosenSlot.slot] = chosenUser.id;
      }
      onChange(JSON.stringify(doc,null,2));
      setMessage(assign ? `Đã điền ${chosenSlot.slot} cho ${currentDept.name}. Hãy lưu bản nháp để cập nhật Database.` : `Đã thêm ${currentDept.name}. Hãy lưu bản nháp.`);
    } catch (error) { setMessage(errorText(error)); }
  }
  return <div className="policy-bindings-assistant">
    <h3>Hỗ trợ phân công theo role</h3>
    <p className="muted">Chỉ hiển thị người đang có quyền APPROVER / EXECUTOR / ACCEPTOR hợp lệ cho loại đơn và phòng ban. Việc chọn không cấp thêm quyền; OPS_ADMIN phải cấp nếu thiếu.</p>
    {candidates.loading && <p>Đang tải người được phân quyền…</p>}
    {candidates.error && <p className="error" role="alert">{candidates.error}</p>}
    {departments.length > 0 && <>
      <div className="form-grid">
        <label>Phòng ban
          <select value={currentDept?.id || ""} onChange={(event) => {setDeptId(event.target.value);setUserId("");}}>
            {departments.map(d=><option value={d.id} key={d.id}>{d.name}</option>)}
          </select>
        </label>
        {requested.length>0 && <label>Vai trò cần gán
          <select value={chosenSlot?.slot || ""} onChange={(event) => {setSlotName(event.target.value);setUserId("");}}>
            {requested.map(s=><option key={`${s.slot}-${s.role}`} value={s.slot}>{s.slot} · {s.role}</option>)}
          </select>
        </label>}
        {requested.length>0 && <label>Người có role hợp lệ
          <select value={chosenUser?.id || ""} onChange={(event) => setUserId(event.target.value)}>
            {validUsers.length===0 && <option value="">Chưa được cấp quyền phù hợp</option>}
            {validUsers.map(u=><option key={u.id} value={u.id}>{u.name} ({u.roles.join(", ")})</option>)}
          </select>
        </label>}
      </div>
      <div className="actions">
        <button type="button" className="secondary" onClick={()=>updateBinding(false)}>Thêm phòng ban</button>
        {requested.length>0 && <button type="button" className="secondary" disabled={!chosenUser} onClick={()=>updateBinding(true)}>Gán người vào JSON</button>}
      </div>
      {!!message && <p role="status" className="muted">{message}</p>}
    </>}
    {!candidates.loading && departments.length===0 && !candidates.error && <p className="muted">Không có phòng ban trong phạm vi POLICY_ADMIN. Kiểm tra role membership trước khi công bố.</p>}
  </div>;
}
