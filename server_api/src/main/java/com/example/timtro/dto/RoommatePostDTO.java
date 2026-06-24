package com.example.timtro.dto;

import com.example.timtro.dto.response.UserProfileDTO;
import com.example.timtro.entity.RoommatePostType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

@Data
@Builder
public class RoommatePostDTO {
    private UUID id;
    private UserProfileDTO user;
    private UserLifestyleDTO lifestyle;
    private RoommatePostType postType;
    private UUID listingId; // Null if NEED_ROOM
    private String title;
    private String description;
    private Double budget;
    private LocalDateTime createdAt;

    @Data
    public static class Request {
        @NotNull
        private RoommatePostType postType;
        
        private UUID listingId;
        
        @NotBlank
        private String title;
        
        @NotBlank
        private String description;
        
        @NotNull
        private Double budget;
    }
}
