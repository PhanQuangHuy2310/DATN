import { Routes, Route, NavLink } from 'react-router-dom';
import { Home, Users, FileText, AlertTriangle, ShieldCheck } from 'lucide-react';
import DashboardPage from './pages/DashboardPage';
import UserManagementPage from './pages/UserManagementPage';
import ListingModerationPage from './pages/ListingModerationPage';
import ReportManagementPage from './pages/ReportManagementPage';
import VerificationPage from './pages/VerificationPage';

function AppLayout() {
  return (
    <div className="flex h-screen bg-paper text-ink font-sans">
      {/* Sidebar */}
      <aside className="w-64 bg-white/70 backdrop-blur-md border-r border-line flex flex-col transition-all">
        <div className="p-6 border-b border-line flex items-center gap-2">
          <div className="size-8 rounded-full bg-cobalt flex items-center justify-center text-white font-bold tracking-tight">NT</div>
          <h1 className="text-xl font-bold text-ink">Tìm Trọ Admin</h1>
        </div>
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto flex flex-col">
          <NavLink to="/" end className={({isActive}) => `flex items-center space-x-3 p-3 rounded-[8.8px] font-medium transition-colors ${isActive ? 'bg-cobalt-soft text-cobalt' : 'text-graphite hover:bg-white hover:text-ink'}`}>
            <Home className="w-5 h-5" />
            <span>Dashboard</span>
          </NavLink>
          <NavLink to="/users" className={({isActive}) => `flex items-center space-x-3 p-3 rounded-[8.8px] font-medium transition-colors ${isActive ? 'bg-cobalt-soft text-cobalt' : 'text-graphite hover:bg-white hover:text-ink'}`}>
            <Users className="w-5 h-5" />
            <span>Quản lý người dùng</span>
          </NavLink>
          <NavLink to="/listings" className={({isActive}) => `flex items-center space-x-3 p-3 rounded-[8.8px] font-medium transition-colors ${isActive ? 'bg-cobalt-soft text-cobalt' : 'text-graphite hover:bg-white hover:text-ink'}`}>
            <FileText className="w-5 h-5" />
            <span>Duyệt tin đăng</span>
          </NavLink>
          <NavLink to="/reports" className={({isActive}) => `flex items-center space-x-3 p-3 rounded-[8.8px] font-medium transition-colors ${isActive ? 'bg-error-soft text-error' : 'text-graphite hover:bg-white hover:text-error'}`}>
            <AlertTriangle className="w-5 h-5" />
            <span>Xử lý báo cáo</span>
          </NavLink>
          <NavLink to="/verifications" className={({isActive}) => `flex items-center space-x-3 p-3 rounded-[8.8px] font-medium transition-colors ${isActive ? 'bg-cobalt-soft text-cobalt' : 'text-graphite hover:bg-white hover:text-ink'}`}>
            <ShieldCheck className="w-5 h-5" />
            <span>Duyệt xác minh</span>
          </NavLink>
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 p-8 overflow-y-auto">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/users" element={<UserManagementPage />} />
          <Route path="/listings" element={<ListingModerationPage />} />
          <Route path="/reports" element={<ReportManagementPage />} />
          <Route path="/verifications" element={<VerificationPage />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return <AppLayout />;
}

export default App;
