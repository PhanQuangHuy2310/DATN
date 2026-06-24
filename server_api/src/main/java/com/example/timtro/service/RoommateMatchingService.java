package com.example.timtro.service;

import com.example.timtro.dto.RoommatePostDTO;
import com.example.timtro.dto.UserLifestyleDTO;
import com.example.timtro.dto.response.UserProfileDTO;
import com.example.timtro.entity.*;
import com.example.timtro.repository.ListingRepository;
import com.example.timtro.repository.RoommatePostRepository;
import com.example.timtro.repository.UserLifestyleRepository;
import com.example.timtro.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class RoommateMatchingService {

    private final UserRepository userRepository;
    private final UserLifestyleRepository userLifestyleRepository;
    private final RoommatePostRepository roommatePostRepository;
    private final ListingRepository listingRepository;

    @Transactional
    public UserLifestyleDTO updateLifestyle(UUID userId, UserLifestyleDTO request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("User not found"));

        UserLifestyle lifestyle = userLifestyleRepository.findById(userId)
                .orElse(UserLifestyle.builder().userId(userId).user(user).build());

        if (request.getCleanliness() != null) lifestyle.setCleanliness(request.getCleanliness());
        if (request.getExtroversion() != null) lifestyle.setExtroversion(request.getExtroversion());
        if (request.getEarlyBird() != null) lifestyle.setEarlyBird(request.getEarlyBird());
        if (request.getCooking() != null) lifestyle.setCooking(request.getCooking());
        if (request.getGuestTolerance() != null) lifestyle.setGuestTolerance(request.getGuestTolerance());

        lifestyle = userLifestyleRepository.save(lifestyle);
        return mapLifestyle(lifestyle);
    }

    @Transactional(readOnly = true)
    public UserLifestyleDTO getLifestyle(UUID userId) {
        return userLifestyleRepository.findById(userId)
                .map(this::mapLifestyle)
                .orElse(null);
    }

    @Transactional
    public RoommatePostDTO createPost(UUID userId, RoommatePostDTO.Request request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("User not found"));

        Listing listing = null;
        if (request.getPostType() == RoommatePostType.HAVE_ROOM) {
            if (request.getListingId() == null) {
                throw new IllegalArgumentException("Listing ID is required when HAVE_ROOM");
            }
            listing = listingRepository.findById(request.getListingId())
                    .orElseThrow(() -> new IllegalArgumentException("Listing not found"));
        }

        RoommatePost post = RoommatePost.builder()
                .user(user)
                .postType(request.getPostType())
                .listing(listing)
                .title(request.getTitle())
                .description(request.getDescription())
                .budget(request.getBudget())
                .isActive(true)
                .build();

        post = roommatePostRepository.save(post);
        return mapPost(post);
    }

    @Transactional(readOnly = true)
    public Page<RoommatePostDTO> getActivePosts(Pageable pageable) {
        return roommatePostRepository.findByIsActiveTrueOrderByCreatedAtDesc(pageable)
                .map(this::mapPost);
    }

    private UserLifestyleDTO mapLifestyle(UserLifestyle entity) {
        return UserLifestyleDTO.builder()
                .cleanliness(entity.getCleanliness())
                .extroversion(entity.getExtroversion())
                .earlyBird(entity.getEarlyBird())
                .cooking(entity.getCooking())
                .guestTolerance(entity.getGuestTolerance())
                .build();
    }

    private RoommatePostDTO mapPost(RoommatePost entity) {
        UserProfileDTO userProfile = UserProfileDTO.builder()
                .id(entity.getUser().getId())
                .email(entity.getUser().getEmail())
                .fullName(entity.getUser().getFullName() != null ? entity.getUser().getFullName() : "Người dùng")
                .avatarUrl(entity.getUser().getAvatarUrl())
                .verified(entity.getUser().getVerified())
                .build();

        UserLifestyleDTO lifestyleDTO = userLifestyleRepository.findById(entity.getUser().getId())
                .map(this::mapLifestyle).orElse(null);

        return RoommatePostDTO.builder()
                .id(entity.getId())
                .user(userProfile)
                .lifestyle(lifestyleDTO)
                .postType(entity.getPostType())
                .listingId(entity.getListing() != null ? entity.getListing().getId() : null)
                .title(entity.getTitle())
                .description(entity.getDescription())
                .budget(entity.getBudget())
                .createdAt(entity.getCreatedAt())
                .build();
    }
}
