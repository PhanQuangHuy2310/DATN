package com.example.timtro.dto;

import com.example.timtro.dto.response.UserProfileDTO;
import com.example.timtro.entity.VerificationStatus;
import jakarta.validation.constraints.NotBlank;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

@Data
@Builder
public class VerificationRequestDTO {
    private UUID id;
    private UserProfileDTO user;
    private String identityCardUrl;
    private String ownershipProofUrl;
    private VerificationStatus status;
    private String adminNote;
    private LocalDateTime createdAt;

    @Data
    public static class CreateRequest {
        @NotBlank(message = "Ảnh CCCD không được để trống")
        private String identityCardUrl;

        @NotBlank(message = "Giấy tờ minh chứng không được để trống")
        private String ownershipProofUrl;
    }

    @Data
    public static class ProcessRequest {
        @NotBlank(message = "Trạng thái không được để trống")
        private String status; // APPROVED, REJECTED
        
        private String adminNote;
    }
}
