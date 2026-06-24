package com.example.timtro.repository;

import com.example.timtro.entity.VerificationRequest;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface VerificationRequestRepository extends JpaRepository<VerificationRequest, UUID> {
    Page<VerificationRequest> findAllByOrderByCreatedAtDesc(Pageable pageable);
    boolean existsByUserIdAndStatus(UUID userId, com.example.timtro.entity.VerificationStatus status);
}
