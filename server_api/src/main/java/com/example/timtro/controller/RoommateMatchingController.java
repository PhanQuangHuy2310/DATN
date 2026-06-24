package com.example.timtro.controller;

import com.example.timtro.dto.RoommatePostDTO;
import com.example.timtro.dto.UserLifestyleDTO;
import com.example.timtro.service.RoommateMatchingService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/roommates")
@RequiredArgsConstructor
public class RoommateMatchingController {

    private final RoommateMatchingService matchingService;

    @GetMapping("/lifestyle")
    public ResponseEntity<UserLifestyleDTO> getMyLifestyle(@AuthenticationPrincipal Jwt jwt) {
        UUID userId = UUID.fromString(jwt.getSubject());
        UserLifestyleDTO lifestyle = matchingService.getLifestyle(userId);
        return ResponseEntity.ok(lifestyle);
    }

    @PutMapping("/lifestyle")
    public ResponseEntity<UserLifestyleDTO> updateMyLifestyle(
            @AuthenticationPrincipal Jwt jwt,
            @Valid @RequestBody UserLifestyleDTO request) {
        UUID userId = UUID.fromString(jwt.getSubject());
        return ResponseEntity.ok(matchingService.updateLifestyle(userId, request));
    }

    @PostMapping("/posts")
    public ResponseEntity<RoommatePostDTO> createPost(
            @AuthenticationPrincipal Jwt jwt,
            @Valid @RequestBody RoommatePostDTO.Request request) {
        UUID userId = UUID.fromString(jwt.getSubject());
        return ResponseEntity.ok(matchingService.createPost(userId, request));
    }

    @GetMapping("/posts")
    public ResponseEntity<Page<RoommatePostDTO>> getPosts(Pageable pageable) {
        return ResponseEntity.ok(matchingService.getActivePosts(pageable));
    }
}
