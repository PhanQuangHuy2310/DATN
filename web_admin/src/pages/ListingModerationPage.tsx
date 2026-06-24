import { useState, useEffect } from 'react';
import { Search, MapPin, CheckCircle, XCircle, Clock, Check, X, RefreshCw, AlertCircle } from 'lucide-react';
import { adminService, ListingAdminDTO } from '../services/adminService';

export default function ListingModerationPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [listings, setListings] = useState<ListingAdminDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchListings = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await adminService.getAllListings();
      setListings(data);
    } catch (err: any) {
      console.error('Failed to fetch listings:', err);
      setError('Lỗi khi tải danh sách tin đăng. Vui lòng thử lại sau.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchListings();
  }, []);

  const handleAction = async (id: string, action: 'APPROVE' | 'REJECT') => {
    setActionLoading(id);
    try {
      const newStatus = action === 'APPROVE' ? 'AVAILABLE' : 'REJECTED';
      await adminService.changeListingStatus(id, newStatus);
      setListings(listings.map(listing => {
        if (listing.id === id) {
          return { ...listing, status: newStatus };
        }
        return listing;
      }));
    } catch (err) {
      console.error('Failed to change status', err);
      alert('Cập nhật trạng thái thất bại!');
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'PENDING':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800"><Clock className="w-3 h-3 mr-1" /> Chờ duyệt</span>;
      case 'AVAILABLE':
      case 'APPROVED':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800"><CheckCircle className="w-3 h-3 mr-1" /> Đã duyệt</span>;
      case 'REJECTED':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"><XCircle className="w-3 h-3 mr-1" /> Đã từ chối</span>;
      case 'RENTED':
      case 'HIDDEN':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800"><CheckCircle className="w-3 h-3 mr-1" /> Đã ẩn/Đã cho thuê</span>;
      default:
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">{status}</span>;
    }
  };

  const filteredListings = listings.filter(listing => {
    const matchesSearch = listing.title.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          listing.ownerName.toLowerCase().includes(searchTerm.toLowerCase());
    
    if (statusFilter === 'ALL') return matchesSearch;
    if (statusFilter === 'PENDING') return matchesSearch && listing.status === 'PENDING';
    if (statusFilter === 'APPROVED') return matchesSearch && (listing.status === 'AVAILABLE' || listing.status === 'APPROVED');
    if (statusFilter === 'REJECTED') return matchesSearch && listing.status === 'REJECTED';
    
    return matchesSearch;
  });

  return (
    <div className="max-w-6xl">
      <div className="mb-8 flex flex-col sm:flex-row gap-4 sm:items-end justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-ink">Duyệt tin đăng</h2>
          <p className="text-fog mt-1">Kiểm tra và phê duyệt các tin đăng mới từ người cho thuê.</p>
        </div>
        <button 
          onClick={fetchListings}
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
            placeholder="Tìm kiếm theo tiêu đề hoặc người đăng..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        
        <div className="flex bg-paper p-1 rounded-lg border border-line w-full md:w-auto overflow-x-auto">
          <button
            onClick={() => setStatusFilter('ALL')}
            className={`flex-none px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
              statusFilter === 'ALL' ? 'bg-white text-ink shadow-sm' : 'text-fog hover:text-graphite'
            }`}
          >
            Tất cả
          </button>
          <button
            onClick={() => setStatusFilter('PENDING')}
            className={`flex-none px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
              statusFilter === 'PENDING' ? 'bg-white text-amber-700 shadow-sm' : 'text-amber-600 hover:text-amber-700'
            }`}
          >
            Chờ duyệt
          </button>
          <button
            onClick={() => setStatusFilter('APPROVED')}
            className={`flex-none px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
              statusFilter === 'APPROVED' ? 'bg-white text-emerald-700 shadow-sm' : 'text-emerald-600 hover:text-emerald-700'
            }`}
          >
            Đã duyệt
          </button>
          <button
            onClick={() => setStatusFilter('REJECTED')}
            className={`flex-none px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
              statusFilter === 'REJECTED' ? 'bg-white text-red-700 shadow-sm' : 'text-red-600 hover:text-red-700'
            }`}
          >
            Từ chối
          </button>
        </div>
      </div>

      {/* Listings Grid */}
      {loading ? (
        <div className="py-12 text-center text-fog flex flex-col items-center">
          <RefreshCw className="w-8 h-8 animate-spin mb-2" />
          <p>Đang tải dữ liệu...</p>
        </div>
      ) : filteredListings.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {filteredListings.map((listing) => (
            <div key={listing.id} className="bg-white/60 backdrop-blur-md rounded-[12px] border border-line overflow-hidden card-hover flex flex-col">
              <div className="relative h-48">
                <img src={listing.imageUrl} alt={listing.title} className="w-full h-full object-cover" />
                <div className="absolute top-3 left-3">
                  {getStatusBadge(listing.status)}
                </div>
                <div className="absolute bottom-3 right-3 bg-black/60 backdrop-blur-sm text-white px-2.5 py-1 rounded-md text-sm font-medium">
                  {new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(listing.price)}/tháng
                </div>
              </div>
              
              <div className="p-5 flex-1 flex flex-col">
                <h3 className="text-lg font-bold text-ink leading-tight mb-2 line-clamp-2">{listing.title}</h3>
                
                <div className="flex items-center text-sm text-fog mb-4 gap-4">
                  <div className="flex items-center">
                    <span className="font-medium mr-1">{listing.area}</span> m²
                  </div>
                  <div className="flex items-center truncate">
                    <MapPin className="w-3.5 h-3.5 mr-1 flex-shrink-0" />
                    <span className="truncate" title={listing.address}>{listing.address}</span>
                  </div>
                </div>
                
                <div className="mt-auto pt-4 border-t border-line flex items-center justify-between">
                  <div className="flex items-center">
                    <div className="h-8 w-8 rounded-full bg-cobalt-soft text-cobalt flex items-center justify-center font-bold text-xs mr-2">
                      {listing.ownerName.charAt(0)}
                    </div>
                    <div className="text-sm">
                      <p className="font-medium text-ink leading-none">{listing.ownerName}</p>
                      <p className="text-xs text-fog mt-1">
                        {new Date(listing.createdAt).toLocaleDateString('vi-VN')}
                      </p>
                    </div>
                  </div>
                  
                  {listing.status === 'PENDING' && (
                    <div className="flex gap-2">
                      <button 
                        onClick={() => handleAction(listing.id, 'REJECT')}
                        disabled={actionLoading === listing.id}
                        className="p-1.5 text-error bg-error-soft rounded-lg hover:bg-red-200 transition-colors disabled:opacity-50"
                        title="Từ chối"
                      >
                        {actionLoading === listing.id ? <RefreshCw className="w-5 h-5 animate-spin" /> : <X className="w-5 h-5" />}
                      </button>
                      <button 
                        onClick={() => handleAction(listing.id, 'APPROVE')}
                        disabled={actionLoading === listing.id}
                        className="p-1.5 text-emerald-600 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-colors disabled:opacity-50"
                        title="Phê duyệt"
                      >
                        {actionLoading === listing.id ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Check className="w-5 h-5" />}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white/60 backdrop-blur-md rounded-[12px] border border-line py-16 text-center">
          <FileText className="w-12 h-12 text-slate-200 mx-auto mb-3" />
          <p className="text-fog">Không tìm thấy tin đăng nào phù hợp</p>
        </div>
      )}
    </div>
  );
}
