package com.example.timtro.dto;

import com.example.timtro.dto.response.UserProfileDTO;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

@Data
@Builder
public class ReviewDTO {
    private UUID id;
    private UUID listingId;
    private UserProfileDTO tenant;
    private Integer rating;
    private String comment;
    private String reply;
    private LocalDateTime createdAt;

    @Data
    public static class CreateRequest {
        @NotNull(message = "ID tin đăng không được để trống")
        private UUID listingId;

        @NotNull(message = "Đánh giá sao không được để trống")
        @Min(value = 1, message = "Đánh giá tối thiểu 1 sao")
        @Max(value = 5, message = "Đánh giá tối đa 5 sao")
        private Integer rating;

        private String comment;
    }

    @Data
    public static class ReplyRequest {
        @NotNull(message = "Nội dung phản hồi không được để trống")
        private String reply;
    }
}
