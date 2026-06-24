package com.example.timtro.service;

import com.example.timtro.dto.ReviewDTO;
import com.example.timtro.dto.response.UserProfileDTO;
import com.example.timtro.entity.Listing;
import com.example.timtro.entity.Review;
import com.example.timtro.entity.User;
import com.example.timtro.repository.AppointmentRepository;
import com.example.timtro.repository.ListingRepository;
import com.example.timtro.repository.ReviewRepository;
import com.example.timtro.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class ReviewService {
    private final ReviewRepository reviewRepository;
    private final ListingRepository listingRepository;
    private final UserRepository userRepository;
    private final AppointmentRepository appointmentRepository;

    @Transactional
    public ReviewDTO createReview(UUID tenantId, ReviewDTO.CreateRequest request) {
        Listing listing = listingRepository.findById(request.getListingId())
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy tin đăng"));

        User tenant = userRepository.findById(tenantId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy user"));

        // Rule: Only tenants with SUCCESS appointments can review.
        boolean hasSuccessAppointment = appointmentRepository.existsByListingIdAndTenantIdAndStatus(
                listing.getId(), tenantId, com.example.timtro.entity.AppointmentStatus.SUCCESS);

        if (!hasSuccessAppointment) {
            throw new AccessDeniedException("Bạn phải xem phòng thành công mới được đánh giá.");
        }

        if (reviewRepository.existsByListingIdAndTenantId(listing.getId(), tenantId)) {
            throw new IllegalArgumentException("Bạn đã đánh giá phòng này rồi.");
        }

        Review review = Review.builder()
                .listing(listing)
                .tenant(tenant)
                .rating(request.getRating())
                .comment(request.getComment())
                .build();

        review = reviewRepository.save(review);
        updateLandlordTrustScore(listing.getUser().getId());
        return mapToDTO(review);
    }

    @Transactional
    public ReviewDTO replyToReview(UUID landlordId, UUID reviewId, ReviewDTO.ReplyRequest request) {
        Review review = reviewRepository.findById(reviewId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy đánh giá"));

        if (!review.getListing().getUser().getId().equals(landlordId)) {
            throw new AccessDeniedException("Bạn không có quyền trả lời đánh giá này");
        }

        review.setReply(request.getReply());
        review = reviewRepository.save(review);
        return mapToDTO(review);
    }

    public Page<ReviewDTO> getListingReviews(UUID listingId, Pageable pageable) {
        return reviewRepository.findByListingIdOrderByCreatedAtDesc(listingId, pageable)
                .map(this::mapToDTO);
    }

    private void updateLandlordTrustScore(UUID landlordId) {
        Double avgRating = reviewRepository.getAverageRatingForLandlord(landlordId);
        // Assuming trust score is stored in user profile or calculated dynamically.
        // For now, we can just log or update user table if there is a column.
    }

    private ReviewDTO mapToDTO(Review review) {
        UserProfileDTO tenantDTO = UserProfileDTO.builder()
                .id(review.getTenant().getId())
                .email(review.getTenant().getEmail())
                .fullName(review.getTenant().getFullName() != null ? review.getTenant().getFullName() : "Người dùng")
                .avatarUrl(review.getTenant().getAvatarUrl())
                .verified(review.getTenant().getVerified())
                .build();

        return ReviewDTO.builder()
                .id(review.getId())
                .listingId(review.getListing().getId())
                .tenant(tenantDTO)
                .rating(review.getRating())
                .comment(review.getComment())
                .reply(review.getReply())
                .createdAt(review.getCreatedAt())
                .build();
    }
}
