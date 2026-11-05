import { useState } from "react";
import { api } from "../api.js";
import { getPrimaryRoleBadge, roles } from "../domain.js";
import { PageHeader } from "./design.jsx";
import { ActionForm } from "./ui.jsx";
import { PasswordField } from "./ux.jsx";

function checkPasswordRules(pwd, email = "") {
  const emailPrefix = String(email || "").split("@")[0].toLowerCase();
  return [
    ["length", "Độ dài từ 15 đến 128 ký tự", pwd.length >= 15 && pwd.length <= 128],
    ["upper", "Có ít nhất 1 chữ cái in hoa (A–Z)", /[A-Z]/.test(pwd)],
    ["lower", "Có ít nhất 1 chữ cái viết thường (a–z)", /[a-z]/.test(pwd)],
    ["digit", "Có ít nhất 1 chữ số (0–9)", /[0-9]/.test(pwd)],
    ["special", "Có ít nhất 1 ký tự đặc biệt (!@#$…)", /[^\p{L}\p{N}]/u.test(pwd)],
    [
      "noEmail",
      "Không chứa tên định danh email của bạn",
      Boolean(pwd.length > 0 && (!emailPrefix || !pwd.toLowerCase().includes(emailPrefix))),
    ],
  ];
}

export function Profile({ user, onChanged }) {
  const [done, setDone] = useState(false);
  const [draftPwd, setDraftPwd] = useState("");
  const roleBadge = getPrimaryRoleBadge(user.roles);
  const wsCode = (user.working_status?.code || "DANG_LAM").toLowerCase();
  const wsLabel = user.working_status?.label || "Đang làm việc";
  const wsDetail = user.working_status?.detail || "";
  const departmentLabel =
    user.department_name ||
    (user.department_code ? `Phòng ${user.department_code}` : "Chưa phân bổ phòng ban");
  const managerLabel = user.manager_name || "Báo cáo trực tiếp Ban Giám đốc";
  const initials = (user.display_name || user.email || "NV")
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
  const rules = checkPasswordRules(draftPwd, user.email);

  return (
    <div className="client-section ds-profile-page">
      <PageHeader
        eyebrow="TÀI KHOẢN & BẢO MẬT"
        title="Hồ sơ cá nhân"
        description="Thông tin định danh nhân sự, đơn vị công tác, vai trò hệ thống và thiết lập bảo mật tài khoản."
      />

      <div className="ds-profile-grid">
        <section className="panel ds-profile-identity-card" aria-label="Thông tin nhân sự">
          <div className="ds-profile-hero">
            <div className="ds-profile-avatar" aria-hidden="true">
              {initials}
            </div>
            <div className="ds-profile-hero-text">
              <h2>{user.display_name || "Nhân sự hệ thống"}</h2>
              <p className="muted">{user.job_title || roleBadge.name}</p>
              <div className="ds-profile-badges">
                <span className={`working-status-badge ws-${wsCode}`}>
                  {wsLabel}
                </span>
                {(user.roles || []).map((r) => (
                  <span key={r} className="ds-role-chip">
                    {roles[r] || r}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {wsDetail && <p className="ds-profile-status-note">{wsDetail}</p>}

          <dl className="data-list ds-profile-details">
            <div>
              <dt>Mã nhân viên</dt>
              <dd>
                <strong>{user.employee_code || "Chưa cấp mã"}</strong>
              </dd>
            </div>
            <div>
              <dt>Email công vụ</dt>
              <dd>{user.email || "—"}</dd>
            </div>
            <div>
              <dt>Phòng ban trực thuộc</dt>
              <dd>
                <strong>{departmentLabel}</strong>
                {user.department_code && (
                  <small className="muted"> ({user.department_code})</small>
                )}
              </dd>
            </div>
            <div>
              <dt>Quản lý trực tiếp</dt>
              <dd>{managerLabel}</dd>
            </div>
          </dl>
        </section>

        <section className="panel ds-profile-security-card" aria-label="Đổi mật khẩu">
          <div className="section-head">
            <div>
              <h2>Đổi mật khẩu bảo mật</h2>
              <p className="muted">
                Áp dụng tiêu chuẩn mật khẩu doanh nghiệp để bảo vệ chữ ký phê duyệt của bạn.
              </p>
            </div>
          </div>

          <div onInput={(e) => {
            if (e.target?.name === "new_password") {
              setDraftPwd(e.target.value || "");
            }
          }}>
            <ActionForm
              submitLabel="Đổi mật khẩu"
              onSubmit={async (v) => {
                setDone(false);
                if (v.new_password !== v.confirm_password) {
                  throw new Error("Mật khẩu xác nhận không khớp với mật khẩu mới.");
                }
                const pwd = v.new_password;
                if (
                  pwd.length < 15 ||
                  pwd.length > 128 ||
                  !/[a-z]/.test(pwd) ||
                  !/[A-Z]/.test(pwd) ||
                  !/[0-9]/.test(pwd) ||
                  !/[^\p{L}\p{N}]/u.test(pwd) ||
                  (user.email &&
                    pwd.toLowerCase().includes(user.email.split("@")[0].toLowerCase()))
                ) {
                  throw new Error(
                    "Mật khẩu mới cần dài 15–128 ký tự, gồm chữ hoa, chữ thường, chữ số, ký tự đặc biệt và không chứa phần tên trước @ của email.",
                  );
                }
                await api("/api/v1/auth/password", {
                  method: "POST",
                  body: JSON.stringify({
                    current_password: v.current_password,
                    new_password: v.new_password,
                  }),
                });
                setDraftPwd("");
                setDone(true);
                if (onChanged) await onChanged();
              }}
            >
              <PasswordField
                label="Mật khẩu hiện tại"
                name="current_password"
                autoComplete="current-password"
                required
              />
              <PasswordField
                label="Mật khẩu mới"
                name="new_password"
                autoComplete="new-password"
                minLength={15}
                maxLength={128}
                required
                help="Tối thiểu 15 ký tự, kết hợp chữ hoa, chữ thường, số và ký tự đặc biệt."
              />
              <ul className="ds-pwd-checklist" aria-label="Tiêu chuẩn mật khẩu">
                {rules.map(([key, text, ok]) => (
                  <li key={key} className={ok ? "is-met" : ""}>
                    <span aria-hidden="true">{ok ? "✓" : "○"}</span> {text}
                  </li>
                ))}
              </ul>
              <PasswordField
                label="Xác nhận mật khẩu"
                name="confirm_password"
                autoComplete="new-password"
                required
              />
            </ActionForm>
          </div>
          {done && (
            <output className="success">
              Đã cập nhật mật khẩu mới thành công. Phiên đăng nhập hiện tại của bạn đã được làm mới an toàn.
            </output>
          )}
        </section>
      </div>
    </div>
  );
}

export default Profile;

