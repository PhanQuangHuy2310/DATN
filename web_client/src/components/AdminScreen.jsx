import { createContext, Suspense, useContext } from "react";

/** Admin screens are injected by the admin portal entry only, so the employee
 * portal bundle never contains their code. */
export const AdminScreensContext = createContext({});

export default function AdminScreen({ name, ...props }) {
  const Screen = useContext(AdminScreensContext)[name];
  if (!Screen) {
    return (
      <section className="panel" role="note">
        <h1>Chức năng quản trị</h1>
        <p className="muted">Màn hình này chỉ có trong Trung tâm Quản trị.</p>
      </section>
    );
  }
  return (
    <Suspense fallback={<p className="muted" role="status">Đang tải màn hình quản trị…</p>}>
      <Screen {...props} />
    </Suspense>
  );
}
