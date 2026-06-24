package com.example.timtro.dto.response;

import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class PoiDTO {
    private String name;
    private String type;
    private double distanceInMeters;
}
