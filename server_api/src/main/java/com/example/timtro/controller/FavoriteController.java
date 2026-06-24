package com.example.timtro.controller;

import com.example.timtro.dto.response.MessageResponse;
import com.example.timtro.entity.Listing;
import com.example.timtro.service.FavoriteService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/favorites")
@RequiredArgsConstructor
public class FavoriteController {

    private final FavoriteService favoriteService;

    @PostMapping("/{listingId}")
    @PreAuthorize("hasRole('TENANT')")
    public ResponseEntity<MessageResponse> toggleFavorite(
            @PathVariable UUID listingId,
            Authentication authentication) {
        String email = authentication.getName();
        return ResponseEntity.ok(favoriteService.toggleFavorite(email, listingId));
    }

    @GetMapping
    @PreAuthorize("hasRole('TENANT')")
    public ResponseEntity<Page<Listing>> getMyFavorites(
            Authentication authentication,
            Pageable pageable) {
        String email = authentication.getName();
        return ResponseEntity.ok(favoriteService.getMyFavoriteListings(email, pageable));
    }
}
