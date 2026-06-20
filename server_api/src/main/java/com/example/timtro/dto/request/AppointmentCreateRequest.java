package com.example.timtro.dto.request;

import jakarta.validation.constraints.Future;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

@Data
public class AppointmentCreateRequest {
    @NotNull(message = "Listing ID không được để trống")
    private UUID listingId;

    @NotNull(message = "Thời gian hẹn không được để trống")
    @Future(message = "Thời gian hẹn phải ở tương lai")
    private LocalDateTime scheduledAt;

    private String note;
}
