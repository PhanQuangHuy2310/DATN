import { useState } from 'react';
import { Search, Filter, ShieldCheck, Check, X, CreditCard, Image as ImageIcon } from 'lucide-react';

const MOCK_VERIFICATIONS = [
  {
    id: 'V001',
    user: 'Trần Thị B',
    email: 'ttb@gmail.com',
    idCard: '001199012345',
    status: 'PENDING',
    date: '2 giờ trước',
    frontIdUrl: 'https://images.unsplash.com/photo-1628155930542-3c7a64e2c833?w=300&q=80',
    backIdUrl: 'https://images.unsplash.com/photo-1628155930542-3c7a64e2c833?w=300&q=80',
  },
  {
    id: 'V002',
    user: 'Lê Hoàng C',
    email: 'lhc@gmail.com',
    idCard: '030095000123',
    status: 'PENDING',
    date: 'Hôm qua, 09:15',
    frontIdUrl: 'https://images.unsplash.com/photo-1628155930542-3c7a64e2c833?w=300&q=80',
    backIdUrl: 'https://images.unsplash.com/photo-1628155930542-3c7a64e2c833?w=300&q=80',
  }
];

export default function VerificationPage() {
  const [searchTerm, setSearchTerm] = useState('');

  return (
    <div className="max-w-6xl w-full">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-ink flex items-center gap-2">
            <ShieldCheck className="w-7 h-7 text-cobalt" />
            Xác minh danh tính chủ trọ
          </h2>
          <p className="text-fog mt-1">Kiểm tra và đối chiếu CCCD/Giấy tờ nhà để cấp tick xanh</p>
        </div>
        
        <div className="flex gap-3 w-full md:w-auto">
          <div className="relative flex-1 md:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fog" />
            <input 
              type="text" 
              placeholder="Tìm tên hoặc số CCCD..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-white/60 backdrop-blur-sm border border-line rounded-[8.8px] focus:outline-none focus:ring-2 focus:ring-cobalt/50 transition-all"
            />
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-white/60 border border-line rounded-[8.8px] hover:bg-paper transition-colors font-medium">
            <Filter className="w-4 h-4" />
            <span>Bộ lọc</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {MOCK_VERIFICATIONS.map(verify => (
          <div key={verify.id} className="bg-white/60 backdrop-blur-md rounded-[12px] border border-line overflow-hidden shadow-sm card-hover">
            <div className="p-5 border-b border-line flex justify-between items-start">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-cobalt-soft rounded-full flex items-center justify-center text-cobalt font-bold text-lg">
                  {verify.user.charAt(0)}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-ink">{verify.user}</h3>
                  <p className="text-sm text-fog">{verify.email}</p>
                </div>
              </div>
              <div className="bg-warning-soft text-warning px-3 py-1 rounded-full text-xs font-bold shadow-sm">
                ĐANG CHỜ DUYỆT
              </div>
            </div>
            
            <div className="p-5 bg-paper/30">
              <div className="flex items-center justify-between mb-4 bg-white p-3 rounded-[8.8px] border border-line">
                <div className="flex items-center gap-2">
                  <CreditCard className="w-5 h-5 text-graphite" />
                  <span className="text-sm font-medium text-fog">Số CCCD/CMND:</span>
                </div>
                <span className="font-bold text-ink tracking-widest">{verify.idCard}</span>
              </div>
              
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div>
                  <p className="text-xs font-medium text-fog mb-2 flex items-center gap-1"><ImageIcon className="w-3 h-3"/> Mặt trước</p>
                  <div className="aspect-[1.6/1] rounded-[8.8px] overflow-hidden border-2 border-line group cursor-pointer">
                    <img src={verify.frontIdUrl} alt="Mặt trước" className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                  </div>
                </div>
                <div>
                  <p className="text-xs font-medium text-fog mb-2 flex items-center gap-1"><ImageIcon className="w-3 h-3"/> Mặt sau</p>
                  <div className="aspect-[1.6/1] rounded-[8.8px] overflow-hidden border-2 border-line group cursor-pointer">
                    <img src={verify.backIdUrl} alt="Mặt sau" className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                  </div>
                </div>
              </div>
              
              <div className="flex gap-3">
                <button className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-cobalt text-white rounded-[8.8px] font-semibold hover:bg-cobalt/90 hover:-translate-y-0.5 transition-all shadow-md shadow-cobalt/20">
                  <Check className="w-5 h-5" />
                  Duyệt cấp Tick xanh
                </button>
                <button className="flex-none px-4 py-2.5 bg-white border border-line text-error rounded-[8.8px] font-semibold hover:bg-error-soft hover:-translate-y-0.5 transition-all">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
