package com.example.timtro.controller;

import com.example.timtro.dto.ReportDTO;
import com.example.timtro.service.ReportService;
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
@RequestMapping("/api/reports")
@RequiredArgsConstructor
public class ReportController {
    private final ReportService reportService;

    @PostMapping
    @PreAuthorize("hasRole('TENANT')")
    public ResponseEntity<ReportDTO> createReport(
            @AuthenticationPrincipal Jwt jwt,
            @Valid @RequestBody ReportDTO.CreateRequest request) {
        UUID tenantId = UUID.fromString(jwt.getSubject());
        return ResponseEntity.ok(reportService.createReport(tenantId, request));
    }

    @GetMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Page<ReportDTO>> getAllReports(Pageable pageable) {
        return ResponseEntity.ok(reportService.getAllReports(pageable));
    }
}
