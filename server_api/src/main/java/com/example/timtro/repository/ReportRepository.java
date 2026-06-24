package com.example.timtro.repository;

import com.example.timtro.entity.Report;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface ReportRepository extends JpaRepository<Report, UUID> {
    boolean existsByListingIdAndReporterId(UUID listingId, UUID reporterId);
    long countByListingId(UUID listingId);
    Page<Report> findAllByOrderByCreatedAtDesc(Pageable pageable);
}
