import { roleTasks } from "../rolePolicy.js";
import { roles } from "../domain.js";

/** Role-aware action cards, not an authorization boundary. */
export default function RoleTasks({ user, navigate }) {
  const tasks = roleTasks(user.roles, user.capabilities);
  return (
    <section className="panel role-task-board" aria-labelledby="role-task-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">KHÔNG GIAN THEO VAI TRÒ</p>
          <h2 id="role-task-title">Công việc và quyền hạn của bạn</h2>
          <p className="muted">Chỉ hiển thị các module thuộc vai trò hiện tại. Mọi hành động còn được máy chủ kiểm tra scope, người phụ trách và trạng thái.</p>
        </div>
      </div>
      <div className="role-badges" aria-label="Vai trò đang có hiệu lực">
        {user.roles.map((role) => <span key={role} className="role-pill">{roles[role] || role}</span>)}
      </div>
      <div className="role-task-grid">
        {tasks.map((task) => <button type="button" key={task.role + task.page} className="role-task" title={`${task.description} · ${task.uc}`} onClick={() => navigate(task.page)}>
          <span className="role-task-icon" aria-hidden="true">{task.icon}</span>
          <span className="role-task-content"><strong>{task.title}</strong><small>{task.description}</small><em>{task.uc}</em></span>
          <span className="role-task-arrow" aria-hidden="true">→</span>
        </button>)}
        {tasks.length === 0 && <p className="muted">Tài khoản chưa được gán vai trò nghiệp vụ. Liên hệ người quản trị danh tính.</p>}
      </div>
    </section>
  );
}
