import {useMemo} from "react";
import { InfoHint } from "./design.jsx";
import {useResource, ResourceState} from "./ui.jsx";
import {buildAccessMatrix} from "../accessMatrix.js";

/** API capability matrix is descriptive. Grant/revoke remains a backend membership mutation. */
export default function RolePermissionMatrix({onSelectRole}) {
  const definition = useResource("/api/v1/admin/access-matrix");
  const endpoints = useResource("/api/v1/admin/api-catalog");
  const matrix = useMemo(()=>buildAccessMatrix(definition.data?.items || [], endpoints.data?.items || []),[definition.data,endpoints.data]);
  return <section className="panel role-assignment-panel" aria-label="Ma trận vai trò và quyền">
    <div className="section-head"><div><h2>Ma trận phân quyền<InfoHint>Chọn vai trò để xem người đang được cấp hoặc cấp mới theo phòng ban và loại yêu cầu. Ma trận thể hiện khả năng API; quyền thực tế do backend kiểm tra.</InfoHint></h2></div></div>
    <ResourceState resource={definition}><ResourceState resource={endpoints}>
      <div className="table-wrap"><table className="role-assignment-table"><thead><tr><th>Vai trò</th>{matrix.domains.map(domain=><th key={domain}>{domain}</th>)}<th>Quản lý</th></tr></thead><tbody>
        {matrix.rows.map(row=><tr key={row.role}>
          <th scope="row">{row.name}</th>
          {row.cells.map(cell=><td key={cell.domain}><span className={`role-capability role-capability-${cell.kind}`} title={`${cell.reads} quyền xem, ${cell.writes} quyền thao tác`}>
            {cell.kind === "both" ? "Xem & sửa" : cell.kind === "read" ? "Xem" : cell.kind === "write" ? "Thao tác" : "—"}</span></td>)}
          <td><button type="button" className="secondary" onClick={()=>onSelectRole(row.role)}>Chỉnh vai trò</button></td>
        </tr>)}</tbody></table></div>
    </ResourceState></ResourceState>
  </section>;
}
