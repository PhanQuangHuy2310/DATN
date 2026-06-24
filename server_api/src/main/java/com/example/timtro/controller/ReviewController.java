package com.example.timtro.controller;

import com.example.timtro.dto.ReviewDTO;
import com.example.timtro.service.ReviewService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/reviews")
@RequiredArgsConstructor
public class ReviewController {
    private final ReviewService reviewService;

    @GetMapping("/listing/{listingId}")
    public ResponseEntity<Page<ReviewDTO>> getListingReviews(
            @PathVariable UUID listingId,
            Pageable pageable) {
        return ResponseEntity.ok(reviewService.getListingReviews(listingId, pageable));
    }

    @PostMapping
    @PreAuthorize("hasRole('TENANT')")
    public ResponseEntity<ReviewDTO> createReview(
            @AuthenticationPrincipal Jwt jwt,
            @Valid @RequestBody ReviewDTO.CreateRequest request) {
        UUID tenantId = UUID.fromString(jwt.getSubject());
        return ResponseEntity.ok(reviewService.createReview(tenantId, request));
    }

    @PostMapping("/{reviewId}/reply")
    @PreAuthorize("hasRole('LANDLORD')")
    public ResponseEntity<ReviewDTO> replyToReview(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable UUID reviewId,
            @Valid @RequestBody ReviewDTO.ReplyRequest request) {
        UUID landlordId = UUID.fromString(jwt.getSubject());
        return ResponseEntity.ok(reviewService.replyToReview(landlordId, reviewId, request));
    }
}
