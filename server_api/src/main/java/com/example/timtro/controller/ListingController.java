package com.example.timtro.controller;

import com.example.timtro.dto.request.ListingCreateRequest;
import com.example.timtro.dto.response.ListingDistanceProjection;
import com.example.timtro.dto.response.MessageResponse;
import com.example.timtro.entity.User;
import com.example.timtro.repository.UserRepository;
import com.example.timtro.service.ListingService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;
import java.util.Collections;
import java.util.UUID;

@RestController
@RequestMapping("/api/listings")
@RequiredArgsConstructor
public class ListingController {

    private final ListingService listingService;
    private final UserRepository userRepository;

    @PostMapping
    @PreAuthorize("hasRole('LANDLORD')")
    public ResponseEntity<MessageResponse> createListing(@Valid @RequestBody ListingCreateRequest request, Authentication authentication) {
        String email = authentication.getName();
        User currentUser = userRepository.findByEmail(email)
                .orElseThrow(() -> new IllegalArgumentException("User không tồn tại"));

        UUID listingId = listingService.createListing(request, currentUser);
        return ResponseEntity.ok(new MessageResponse("Thêm mới tin đăng thành công. ID: " + listingId));
    }

    @GetMapping("/nearby")
    public ResponseEntity<List<ListingDistanceProjection>> getNearbyListings(
            @RequestParam double lat,
            @RequestParam double lng,
            @RequestParam(defaultValue = "5000") double radius) { // mặc định 5km
        
        List<ListingDistanceProjection> listings = listingService.searchListingsByRadius(lat, lng, radius);
        return ResponseEntity.ok(listings);
    }

    @GetMapping("/latest")
    public ResponseEntity<List<Object>> getLatestListings() {
        return ResponseEntity.ok(Collections.emptyList());
    }

    @GetMapping("/featured")
    public ResponseEntity<List<Object>> getFeaturedListings() {
        return ResponseEntity.ok(Collections.emptyList());
    }

    @GetMapping("/roommates")
    public ResponseEntity<List<Object>> getRoommateListings() {
        return ResponseEntity.ok(Collections.emptyList());
    }

    @GetMapping("/search")
    public ResponseEntity<List<Object>> searchListings() {
        return ResponseEntity.ok(Collections.emptyList());
    }

    // Mock API Gia hạn Premium (Chỉ dùng cho test)
    @PostMapping("/premium/mock-pay")
    @PreAuthorize("hasRole('LANDLORD')")
    public ResponseEntity<MessageResponse> mockPayPremium(Authentication authentication) {
        String email = authentication.getName();
        User currentUser = userRepository.findByEmail(email)
                .orElseThrow(() -> new IllegalArgumentException("User không tồn tại"));

        // Gia hạn 30 ngày kể từ hiện tại
        currentUser.setPremiumExpiryDate(LocalDateTime.now().plusDays(30));
        userRepository.save(currentUser);

        return ResponseEntity.ok(new MessageResponse("Đã gia hạn gói Premium 30 ngày thành công."));
    }
}
