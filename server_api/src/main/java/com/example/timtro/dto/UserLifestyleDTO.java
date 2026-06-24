package com.example.timtro.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class UserLifestyleDTO {
    @Min(1) @Max(5)
    private Integer cleanliness;
    @Min(1) @Max(5)
    private Integer extroversion;
    @Min(1) @Max(5)
    private Integer earlyBird;
    @Min(1) @Max(5)
    private Integer cooking;
    @Min(1) @Max(5)
    private Integer guestTolerance;
}
