/** Client workflow stages are a view over server-owned statuses, never mutations. */
export const WORKFLOW_COLUMNS = [
  { key: "mine", title: "Yêu cầu của tôi", filter: "mine", help: "Hồ sơ bạn đã tạo" },
  { key: "approval", title: "Phê duyệt", filter: "approval", help: "Hồ sơ đến lượt bạn duyệt" },
  { key: "execution", title: "Thực hiện", filter: "execution", help: "Công việc được giao" },
  { key: "acceptance", title: "Nghiệm thu", filter: "acceptance", help: "Hồ sơ cần nghiệm thu" },
  { key: "completed", title: "Hoàn thành", filter: "mine", status: "COMPLETED", help: "Hồ sơ đã hoàn thành của bạn" },
  { key: "drafts", title: "Nháp", filter: "mine", status: "DRAFT", help: "Hồ sơ chưa gửi" },
];
export function allowedStages(user) {
  const roles = user?.roles || [];
  return WORKFLOW_COLUMNS.filter(stage => {
    if (["mine", "completed", "drafts"].includes(stage.key)) return roles.includes("REQUESTER");
    return roles.includes({ approval: "APPROVER", execution: "EXECUTOR", acceptance: "ACCEPTOR" }[stage.key]);
  });
}
export function requestStage(status) {
  if (status === "DRAFT") return "drafts";
  if (status === "REJECTED") return "rejected";
  if (status === "CANCELLED") return "cancelled";
  if (status === "COMPLETED") return "completed";
  if (status === "PENDING_APPROVAL" || status === "NEEDS_INFO") return "approval";
  if (status === "READY_FOR_EXECUTION" || status === "IN_PROGRESS") return "execution";
  if (status === "WAITING_FOR_ACCEPTANCE") return "acceptance";
  return "mine";
}
export const STATUS_STAGES = ["drafts", "approval", "execution", "acceptance", "completed", "rejected", "cancelled"];
