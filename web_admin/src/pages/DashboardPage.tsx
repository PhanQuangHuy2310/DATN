import { useState, useEffect } from 'react';
import { Users, FileText, CheckCircle, BarChart3, AlertCircle, RefreshCw } from 'lucide-react';
import { adminService, StatisticsDTO } from '../services/adminService';

export default function DashboardPage() {
  const [stats, setStats] = useState<StatisticsDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchStats = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await adminService.getStatistics();
      setStats(data);
    } catch (err: any) {
      console.error('Failed to fetch statistics', err);
      setError('Lỗi khi tải dữ liệu thống kê');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  return (
    <div className="max-w-5xl">
      <div className="mb-8 flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-ink">Tổng quan hệ thống</h2>
          <p className="text-fog mt-1">Theo dõi các chỉ số quan trọng của nền tảng.</p>
        </div>
        <button 
          onClick={fetchStats}
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

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Tổng người dùng" 
          value={stats?.totalUsers || 0} 
          icon={<Users className="w-5 h-5 text-cobalt" />}
          loading={loading}
        />
        <StatCard 
          title="Tin chờ duyệt" 
          value={stats?.pendingListings || 0} 
          icon={<FileText className="w-5 h-5 text-warning" />}
          loading={loading}
        />
        <StatCard 
          title="Tổng tin đăng" 
          value={stats?.totalListings || 0} 
          icon={<CheckCircle className="w-5 h-5 text-emerald-600" />}
          loading={loading}
        />
        <StatCard 
          title="Lượt truy cập" 
          value={stats?.totalViews || 0} 
          icon={<BarChart3 className="w-5 h-5 text-purple-600" />}
          loading={loading}
        />
      </div>
    </div>
  );
}

function StatCard({ title, value, icon, loading }: { title: string, value: string | number, icon: React.ReactNode, loading: boolean }) {
  return (
    <div className="group bg-white/60 backdrop-blur-md p-6 rounded-[12px] border border-line card-hover relative overflow-hidden flex flex-col justify-between">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 rounded-[8.8px] bg-paper border border-line flex-shrink-0">
          {icon}
        </div>
        <h3 className="text-graphite text-sm font-medium">{title}</h3>
      </div>
      
      {loading ? (
        <div className="h-9 w-24 rounded skeleton" />
      ) : (
        <p className="text-3xl font-bold text-ink">{value}</p>
      )}
    </div>
  );
}
