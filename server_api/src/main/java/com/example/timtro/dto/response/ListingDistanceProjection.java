package com.example.timtro.dto.response;

import java.util.UUID;

public interface ListingDistanceProjection {
    UUID getId();
    String getTitle();
    Double getPrice();
    Double getArea();
    Double getDistance();
}
