import { useState } from 'react';
import { Search, Filter, AlertOctagon, CheckCircle2, MessageSquareWarning, ExternalLink } from 'lucide-react';

const MOCK_REPORTS = [
  {
    id: 'R001',
    listingTitle: 'Phòng trọ khép kín, có gác xép, full nội thất',
    reporter: 'Nguyễn Văn A',
    reason: 'Tin đăng giả mạo, lừa đảo tiền cọc',
    details: 'Chủ nhà yêu cầu chuyển cọc trước khi xem phòng, số tài khoản không chính chủ.',
    status: 'OPEN',
    date: 'Hôm qua, 14:30',
  },
  {
    id: 'R002',
    listingTitle: 'Căn hộ mini ban công siêu thoáng',
    reporter: 'Lê Hoàng C',
    reason: 'Hình ảnh không đúng sự thật',
    details: 'Đến xem thực tế phòng rất cũ nát, không giống ảnh trên mạng chụp.',
    status: 'OPEN',
    date: '2 ngày trước',
  },
  {
    id: 'R003',
    listingTitle: 'Phòng giá rẻ cho sinh viên ĐH Công Nghiệp',
    reporter: 'Trần Thị B',
    reason: 'Phòng đã cho thuê nhưng không gỡ tin',
    details: 'Tôi gọi điện thì báo đã hết phòng từ tuần trước.',
    status: 'RESOLVED',
    date: '1 tuần trước',
  }
];

export default function ReportManagementPage() {
  const [searchTerm, setSearchTerm] = useState('');

  return (
    <div className="max-w-6xl w-full">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-ink">Xử lý báo cáo vi phạm</h2>
          <p className="text-fog mt-1">Giải quyết khiếu nại từ người dùng để bảo vệ cộng đồng</p>
        </div>
        
        <div className="flex gap-3 w-full md:w-auto">
          <div className="relative flex-1 md:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fog" />
            <input 
              type="text" 
              placeholder="Tìm kiếm mã báo cáo..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-white/60 backdrop-blur-sm border border-line rounded-[8.8px] focus:outline-none focus:ring-2 focus:ring-cobalt/50 transition-all"
            />
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-white/60 border border-line rounded-[8.8px] hover:bg-paper transition-colors font-medium">
            <Filter className="w-4 h-4" />
            <span>Trạng thái</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {MOCK_REPORTS.map(report => (
          <div key={report.id} className="bg-white/60 backdrop-blur-md p-6 rounded-[12px] border border-line card-hover flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-start mb-4">
                <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold
                  ${report.status === 'OPEN' ? 'bg-error-soft text-error' : 'bg-success-soft text-success'}`}>
                  {report.status === 'OPEN' ? <AlertOctagon className="w-3.5 h-3.5" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                  {report.status === 'OPEN' ? 'ĐANG CHỜ XỬ LÝ' : 'ĐÃ GIẢI QUYẾT'}
                </div>
                <span className="text-xs text-fog font-medium">#{report.id}</span>
              </div>
              
              <h3 className="text-lg font-bold text-ink mb-2 line-clamp-1">{report.reason}</h3>
              
              <div className="bg-paper p-3 rounded-[8.8px] mb-4 border border-line">
                <div className="flex gap-2 items-start text-sm">
                  <MessageSquareWarning className="w-4 h-4 text-graphite shrink-0 mt-0.5" />
                  <p className="text-graphite italic line-clamp-3">"{report.details}"</p>
                </div>
              </div>
              
              <div className="space-y-2 mb-6">
                <div className="flex justify-between text-sm">
                  <span className="text-fog">Tin bị báo cáo:</span>
                  <a href="#" className="font-medium text-cobalt hover:underline flex items-center gap-1 truncate max-w-[180px]">
                    {report.listingTitle} <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-fog">Người báo cáo:</span>
                  <span className="font-medium text-ink">{report.reporter}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-fog">Thời gian:</span>
                  <span className="text-ink">{report.date}</span>
                </div>
              </div>
            </div>
            
            <div className="flex gap-2">
              {report.status === 'OPEN' && (
                <>
                  <button className="flex-1 px-4 py-2 bg-error text-white rounded-[8.8px] text-sm font-semibold hover:bg-error/90 transition-colors shadow-sm shadow-error/20">
                    Xóa tin & Phạt
                  </button>
                  <button className="flex-1 px-4 py-2 bg-paper text-graphite border border-line rounded-[8.8px] text-sm font-semibold hover:bg-line/50 transition-colors">
                    Bỏ qua
                  </button>
                </>
              )}
              {report.status === 'RESOLVED' && (
                <button className="w-full px-4 py-2 bg-paper text-fog border border-line rounded-[8.8px] text-sm font-medium hover:bg-line/50 transition-colors">
                  Xem lại lịch sử xử lý
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
