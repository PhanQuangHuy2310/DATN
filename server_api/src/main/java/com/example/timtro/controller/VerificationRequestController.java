package com.example.timtro.controller;

import com.example.timtro.dto.VerificationRequestDTO;
import com.example.timtro.service.VerificationRequestService;
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
@RequestMapping("/api/verification-requests")
@RequiredArgsConstructor
public class VerificationRequestController {
    private final VerificationRequestService verificationRequestService;

    @PostMapping
    @PreAuthorize("hasRole('LANDLORD')")
    public ResponseEntity<VerificationRequestDTO> createRequest(
            @AuthenticationPrincipal Jwt jwt,
            @Valid @RequestBody VerificationRequestDTO.CreateRequest request) {
        UUID landlordId = UUID.fromString(jwt.getSubject());
        return ResponseEntity.ok(verificationRequestService.createRequest(landlordId, request));
    }

    @GetMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Page<VerificationRequestDTO>> getAllRequests(Pageable pageable) {
        return ResponseEntity.ok(verificationRequestService.getAllRequests(pageable));
    }

    @PostMapping("/{requestId}/process")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<VerificationRequestDTO> processRequest(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable UUID requestId,
            @Valid @RequestBody VerificationRequestDTO.ProcessRequest request) {
        UUID adminId = UUID.fromString(jwt.getSubject());
        return ResponseEntity.ok(verificationRequestService.processRequest(adminId, requestId, request));
    }
}
