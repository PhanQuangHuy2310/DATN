package com.example.timtro.dto;

import com.example.timtro.dto.response.UserProfileDTO;
import com.example.timtro.entity.ReportStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

@Data
@Builder
public class ReportDTO {
    private UUID id;
    private UUID listingId;
    private UserProfileDTO reporter;
    private String reason;
    private String description;
    private ReportStatus status;
    private LocalDateTime createdAt;

    @Data
    public static class CreateRequest {
        @NotNull(message = "ID tin đăng không được để trống")
        private UUID listingId;

        @NotBlank(message = "Lý do báo cáo không được để trống")
        private String reason;

        private String description;
    }
}
