import { useState, useEffect } from 'react';
import { Search, User, Ban, CheckCircle2, ShieldCheck, RefreshCw, AlertCircle } from 'lucide-react';
import { adminService, UserAdminDTO } from '../services/adminService';

export default function UserManagementPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [users, setUsers] = useState<UserAdminDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchUsers = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await adminService.getAllUsers();
      // Lọc bỏ role ADMIN để không cho chỉnh sửa theo yêu cầu
      setUsers(data.filter(u => u.role !== 'ADMIN'));
    } catch (err: any) {
      console.error('Failed to fetch users:', err);
      setError('Lỗi khi tải danh sách người dùng. Vui lòng thử lại sau.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleToggleStatus = async (userId: string, currentStatus: string) => {
    setActionLoading(userId);
    const newStatus = currentStatus === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
    try {
      await adminService.changeUserStatus(userId, newStatus);
      setUsers(users.map(u => {
        if (u.id === userId) {
          return { ...u, status: newStatus };
        }
        return u;
      }));
    } catch (err) {
      console.error('Failed to change status', err);
      alert('Thay đổi trạng thái thất bại!');
    } finally {
      setActionLoading(null);
    }
  };

  const filteredUsers = users.filter(user => {
    const matchesSearch = user.fullName.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          user.email.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesRole = roleFilter === 'ALL' || user.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  return (
    <div className="max-w-6xl">
      <div className="mb-8 flex flex-col sm:flex-row gap-4 sm:items-end justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-ink">Quản lý người dùng</h2>
          <p className="text-fog mt-1">Quản lý tài khoản, phân quyền và khóa người dùng vi phạm.</p>
        </div>
        <button 
          onClick={fetchUsers}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-line rounded-lg text-graphite hover:bg-paper transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Làm mới</span>
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg mb-6 flex items-center gap-2">
          <AlertCircle className="w-5 h-5" />
          <p>{error}</p>
        </div>
      )}

      {/* Filters and Search */}
      <div className="bg-white/60 backdrop-blur-md p-4 rounded-[12px] border border-line mb-6 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative w-full md:w-96">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-5 w-5 text-fog" />
          </div>
          <input
            type="text"
            className="block w-full pl-10 pr-3 py-2 border border-line rounded-lg leading-5 bg-white placeholder-fog focus:outline-none focus:ring-1 focus:ring-cobalt focus:border-cobalt sm:text-sm transition-all"
            placeholder="Tìm kiếm theo tên hoặc email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        
        <div className="flex bg-paper p-1 rounded-lg border border-line w-full md:w-auto">
          <button
            onClick={() => setRoleFilter('ALL')}
            className={`flex-1 md:flex-none px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
              roleFilter === 'ALL' ? 'bg-white text-ink shadow-sm' : 'text-fog hover:text-graphite'
            }`}
          >
            Tất cả
          </button>
          <button
            onClick={() => setRoleFilter('TENANT')}
            className={`flex-1 md:flex-none px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
              roleFilter === 'TENANT' ? 'bg-white text-ink shadow-sm' : 'text-fog hover:text-graphite'
            }`}
          >
            Người thuê
          </button>
          <button
            onClick={() => setRoleFilter('LANDLORD')}
            className={`flex-1 md:flex-none px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
              roleFilter === 'LANDLORD' ? 'bg-white text-ink shadow-sm' : 'text-fog hover:text-graphite'
            }`}
          >
            Người cho thuê
          </button>
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white/60 backdrop-blur-md border border-line rounded-[12px] overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-fog flex flex-col items-center">
            <RefreshCw className="w-8 h-8 animate-spin mb-2" />
            <p>Đang tải dữ liệu...</p>
          </div>
        ) : (
          <table className="min-w-full divide-y divide-line">
            <thead className="bg-paper">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-fog uppercase tracking-wider">
                  Người dùng
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-fog uppercase tracking-wider">
                  Vai trò
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-fog uppercase tracking-wider">
                  Bài đăng
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-fog uppercase tracking-wider">
                  Trạng thái
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-line">
              {filteredUsers.length > 0 ? (
                filteredUsers.map((user) => (
                  <tr key={user.id} className="hover:bg-paper/50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-10 w-10">
                          {user.avatarUrl ? (
                            <img className="h-10 w-10 rounded-full object-cover border border-line" src={user.avatarUrl} alt="" />
                          ) : (
                            <div className="h-10 w-10 rounded-full bg-cobalt-soft text-cobalt flex items-center justify-center font-bold">
                              {user.fullName.charAt(0)}
                            </div>
                          )}
                        </div>
                        <div className="ml-4">
                          <div className="text-sm font-medium text-ink">{user.fullName}</div>
                          <div className="text-sm text-fog">{user.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        {user.role === 'LANDLORD' ? (
                          <ShieldCheck className="w-4 h-4 text-emerald-500 mr-1.5" />
                        ) : (
                          <User className="w-4 h-4 text-slate-400 mr-1.5" />
                        )}
                        <span className="text-sm text-graphite">
                          {user.role === 'LANDLORD' ? 'Người cho thuê' : 'Người thuê'}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {user.role === 'LANDLORD' ? (
                        <div className="flex items-center">
                          <span className="text-sm font-medium bg-blue-50 text-blue-700 px-2 py-1 rounded-md border border-blue-200">
                            {user.postCount} tin
                          </span>
                        </div>
                      ) : (
                        <span className="text-sm text-fog">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <button
                        onClick={() => handleToggleStatus(user.id, user.status)}
                        disabled={actionLoading === user.id}
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium cursor-pointer transition-all hover:scale-105 active:scale-95 disabled:opacity-50 disabled:pointer-events-none ${
                          user.status === 'ACTIVE' 
                            ? 'bg-emerald-100 text-emerald-800 hover:bg-red-100 hover:text-red-800 group' 
                            : 'bg-red-100 text-red-800 hover:bg-emerald-100 hover:text-emerald-800 group'
                        }`}
                        title={user.status === 'ACTIVE' ? "Bấm để KHÓA tài khoản" : "Bấm để MỞ KHÓA tài khoản"}
                      >
                        {actionLoading === user.id ? (
                          <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                        ) : user.status === 'ACTIVE' ? (
                          <CheckCircle2 className="w-3 h-3 mr-1 group-hover:hidden" />
                        ) : (
                          <Ban className="w-3 h-3 mr-1 group-hover:hidden" />
                        )}
                        {user.status === 'ACTIVE' ? (
                          <>
                            <span className="group-hover:hidden">Đang hoạt động</span>
                            <span className="hidden group-hover:inline">Khóa tài khoản</span>
                          </>
                        ) : (
                          <>
                            <span className="group-hover:hidden">Đã bị khóa</span>
                            <span className="hidden group-hover:inline">Mở khóa</span>
                          </>
                        )}
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center text-fog">
                    <div className="flex flex-col items-center justify-center">
                      <User className="w-12 h-12 text-slate-200 mb-3" />
                      <p>Không tìm thấy người dùng nào phù hợp</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
