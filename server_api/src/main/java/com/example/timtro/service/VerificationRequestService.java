package com.example.timtro.service;

import com.example.timtro.dto.VerificationRequestDTO;
import com.example.timtro.dto.response.UserProfileDTO;
import com.example.timtro.entity.User;
import com.example.timtro.entity.VerificationRequest;
import com.example.timtro.entity.VerificationStatus;
import com.example.timtro.repository.UserRepository;
import com.example.timtro.repository.VerificationRequestRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class VerificationRequestService {
    private final VerificationRequestRepository verificationRequestRepository;
    private final UserRepository userRepository;

    @Transactional
    public VerificationRequestDTO createRequest(UUID landlordId, VerificationRequestDTO.CreateRequest request) {
        User landlord = userRepository.findById(landlordId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy user"));

        if (verificationRequestRepository.existsByUserIdAndStatus(landlordId, VerificationStatus.PENDING)) {
            throw new IllegalArgumentException("Bạn đã gửi yêu cầu và đang chờ duyệt.");
        }

        VerificationRequest verificationRequest = VerificationRequest.builder()
                .user(landlord)
                .identityCardUrl(request.getIdentityCardUrl())
                .ownershipProofUrl(request.getOwnershipProofUrl())
                .status(VerificationStatus.PENDING)
                .build();

        verificationRequest = verificationRequestRepository.save(verificationRequest);
        return mapToDTO(verificationRequest);
    }

    @Transactional
    public VerificationRequestDTO processRequest(UUID adminId, UUID requestId, VerificationRequestDTO.ProcessRequest request) {
        VerificationRequest verificationRequest = verificationRequestRepository.findById(requestId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy yêu cầu xác minh"));

        VerificationStatus newStatus = VerificationStatus.valueOf(request.getStatus());
        verificationRequest.setStatus(newStatus);
        verificationRequest.setAdminNote(request.getAdminNote());

        if (newStatus == VerificationStatus.APPROVED) {
            User landlord = verificationRequest.getUser();
            landlord.setVerified(true);
            userRepository.save(landlord);
        } else if (newStatus == VerificationStatus.REJECTED) {
            User landlord = verificationRequest.getUser();
            landlord.setVerified(false);
            userRepository.save(landlord);
        }

        verificationRequest = verificationRequestRepository.save(verificationRequest);
        // TODO: Ghi AuditLog việc duyệt yêu cầu
        return mapToDTO(verificationRequest);
    }

    public Page<VerificationRequestDTO> getAllRequests(Pageable pageable) {
        return verificationRequestRepository.findAllByOrderByCreatedAtDesc(pageable)
                .map(this::mapToDTO);
    }

    private VerificationRequestDTO mapToDTO(VerificationRequest verificationRequest) {
        UserProfileDTO userDTO = UserProfileDTO.builder()
                .id(verificationRequest.getUser().getId())
                .email(verificationRequest.getUser().getEmail())
                .fullName(verificationRequest.getUser().getFullName() != null ? verificationRequest.getUser().getFullName() : "Người dùng")
                .avatarUrl(verificationRequest.getUser().getAvatarUrl())
                .verified(verificationRequest.getUser().getVerified())
                .build();

        return VerificationRequestDTO.builder()
                .id(verificationRequest.getId())
                .user(userDTO)
                .identityCardUrl(verificationRequest.getIdentityCardUrl())
                .ownershipProofUrl(verificationRequest.getOwnershipProofUrl())
                .status(verificationRequest.getStatus())
                .adminNote(verificationRequest.getAdminNote())
                .createdAt(verificationRequest.getCreatedAt())
                .build();
    }
}
