package com.example.timtro.service;

import com.example.timtro.dto.ReportDTO;
import com.example.timtro.dto.response.UserProfileDTO;
import com.example.timtro.entity.Listing;
import com.example.timtro.entity.ListingStatus;
import com.example.timtro.entity.Report;
import com.example.timtro.entity.User;
import com.example.timtro.repository.ListingRepository;
import com.example.timtro.repository.ReportRepository;
import com.example.timtro.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class ReportService {
    private final ReportRepository reportRepository;
    private final ListingRepository listingRepository;
    private final UserRepository userRepository;

    // Ngưỡng số lượng report để tự động ẩn bài viết
    private static final int AUTO_HIDE_THRESHOLD = 5;

    @Transactional
    public ReportDTO createReport(UUID reporterId, ReportDTO.CreateRequest request) {
        Listing listing = listingRepository.findById(request.getListingId())
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy tin đăng"));

        User reporter = userRepository.findById(reporterId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy user"));

        if (reportRepository.existsByListingIdAndReporterId(listing.getId(), reporterId)) {
            throw new IllegalArgumentException("Bạn đã báo cáo tin đăng này rồi.");
        }

        Report report = Report.builder()
                .listing(listing)
                .reporter(reporter)
                .reason(request.getReason())
                .description(request.getDescription())
                .build();

        report = reportRepository.save(report);

        // Logic M18: Nếu tin đăng nhận đủ N báo cáo, tự động ẩn
        long reportCount = reportRepository.countByListingId(listing.getId());
        if (reportCount >= AUTO_HIDE_THRESHOLD && listing.getStatus() != ListingStatus.HIDDEN) {
            listing.setStatus(ListingStatus.HIDDEN);
            listingRepository.save(listing);
            // TODO: Ghi AuditLog việc ẩn tự động
        }

        return mapToDTO(report);
    }

    public Page<ReportDTO> getAllReports(Pageable pageable) {
        return reportRepository.findAllByOrderByCreatedAtDesc(pageable)
                .map(this::mapToDTO);
    }

    private ReportDTO mapToDTO(Report report) {
        UserProfileDTO reporterDTO = UserProfileDTO.builder()
                .id(report.getReporter().getId())
                .email(report.getReporter().getEmail())
                .fullName(report.getReporter().getFullName() != null ? report.getReporter().getFullName() : "Người dùng")
                .avatarUrl(report.getReporter().getAvatarUrl())
                .verified(report.getReporter().getVerified())
                .build();

        return ReportDTO.builder()
                .id(report.getId())
                .listingId(report.getListing().getId())
                .reporter(reporterDTO)
                .reason(report.getReason())
                .description(report.getDescription())
                .status(report.getStatus())
                .createdAt(report.getCreatedAt())
                .build();
    }
}
