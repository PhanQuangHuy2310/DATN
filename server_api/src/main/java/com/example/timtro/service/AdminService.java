package com.example.timtro.service;

import com.example.timtro.dto.response.MessageResponse;
import com.example.timtro.entity.AuditLog;
import com.example.timtro.entity.Listing;
import com.example.timtro.entity.ListingStatus;
import com.example.timtro.entity.User;
import com.example.timtro.entity.UserStatus;
import com.example.timtro.repository.AuditLogRepository;
import com.example.timtro.repository.ListingRepository;
import com.example.timtro.repository.UserRepository;
import com.example.timtro.repository.ViewEventRepository;
import com.example.timtro.dto.response.UserAdminDTO;
import com.example.timtro.dto.response.ListingAdminDTO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class AdminService {

    private final UserRepository userRepository;
    private final ListingRepository listingRepository;
    private final AuditLogRepository auditLogRepository;
    private final ViewEventRepository viewEventRepository;

    @Transactional
    public MessageResponse changeUserStatus(UUID userId, UserStatus status, String adminEmail) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy người dùng"));

        user.setStatus(status);
        userRepository.save(user);

        logAction(adminEmail, "CHANGE_USER_STATUS", user.getId(), "Đổi trạng thái thành: " + status);
        return new MessageResponse("Cập nhật trạng thái người dùng thành công");
    }

    @Transactional
    public MessageResponse changeListingStatus(UUID listingId, ListingStatus status, String adminEmail) {
        Listing listing = listingRepository.findById(listingId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy tin đăng"));

        listing.setStatus(status);
        listingRepository.save(listing);

        logAction(adminEmail, "CHANGE_LISTING_STATUS", listing.getId(), "Đổi trạng thái thành: " + status);
        return new MessageResponse("Cập nhật trạng thái tin đăng thành công");
    }

    @Transactional(readOnly = true)
    public List<UserAdminDTO> getAllUsers() {
        return userRepository.findAll().stream().map(user -> UserAdminDTO.builder()
                .id(user.getId())
                .fullName(user.getFullName())
                .email(user.getEmail())
                .role(user.getRole())
                .status(user.getStatus())
                .avatarUrl(user.getAvatarUrl())
                .postCount(listingRepository.countByUser(user))
                .build()
        ).collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public List<ListingAdminDTO> getAllListings() {
        return listingRepository.findAll().stream().map(listing -> ListingAdminDTO.builder()
                .id(listing.getId())
                .title(listing.getTitle())
                .price(listing.getPrice())
                .area(listing.getArea())
                .address("Đã ẩn") // Default fallback if no address mapping
                .ownerName(listing.getUser().getFullName())
                .status(listing.getStatus())
                .createdAt(listing.getCreatedAt())
                .imageUrl("https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=500&q=80") // Placeholder
                .build()
        ).collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public Map<String, Long> getStatistics() {
        long totalUsers = userRepository.count();
        long pendingListings = listingRepository.countByStatus(ListingStatus.PENDING);
        long totalListings = listingRepository.count();
        long totalViews = viewEventRepository.count();
        
        return Map.of(
                "totalUsers", totalUsers,
                "pendingListings", pendingListings,
                "totalListings", totalListings,
                "totalViews", totalViews
        );
    }

    private void logAction(String adminEmail, String action, UUID targetId, String details) {
        AuditLog log = AuditLog.builder()
                .adminEmail(adminEmail)
                .action(action)
                .targetId(targetId)
                .details(details)
                .build();
        auditLogRepository.save(log);
    }
}
