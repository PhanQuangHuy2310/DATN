package com.example.timtro.dto.response;

import lombok.Builder;
import lombok.Data;

import java.util.List;

@Data
@Builder
public class MidpointSearchResponseDTO {
    private com.example.timtro.dto.request.CoordinateDTO midpoint;
    private List<ListingDistanceProjection> listings;
}
