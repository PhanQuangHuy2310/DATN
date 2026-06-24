package com.example.timtro.controller;

import com.example.timtro.dto.response.MessageResponse;
import com.example.timtro.entity.ListingStatus;
import com.example.timtro.entity.UserStatus;
import com.example.timtro.service.AdminService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
public class AdminController {

    private final AdminService adminService;

    @PatchMapping("/users/{id}/status")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<MessageResponse> changeUserStatus(
            @PathVariable UUID id,
            @RequestParam UserStatus status,
            Authentication authentication) {
        String adminEmail = authentication.getName();
        return ResponseEntity.ok(adminService.changeUserStatus(id, status, adminEmail));
    }

    @PatchMapping("/listings/{id}/status")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<MessageResponse> changeListingStatus(
            @PathVariable UUID id,
            @RequestParam ListingStatus status,
            Authentication authentication) {
        String adminEmail = authentication.getName();
        return ResponseEntity.ok(adminService.changeListingStatus(id, status, adminEmail));
    }

    @GetMapping("/users")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<com.example.timtro.dto.response.UserAdminDTO>> getAllUsers() {
        return ResponseEntity.ok(adminService.getAllUsers());
    }

    @GetMapping("/listings")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<com.example.timtro.dto.response.ListingAdminDTO>> getAllListings() {
        return ResponseEntity.ok(adminService.getAllListings());
    }

    @GetMapping("/statistics")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Map<String, Long>> getStatistics() {
        return ResponseEntity.ok(adminService.getStatistics());
    }
}
