package com.example.timtro.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class ListingCreateRequest {

    @NotBlank(message = "Tiêu đề không được để trống")
    private String title;

    private String description;

    @NotNull(message = "Giá không được để trống")
    private Double price;

    @NotNull(message = "Diện tích không được để trống")
    private Double area;

    @NotNull(message = "Kinh độ (lng) không được để trống")
    private Double lng;

    @NotNull(message = "Vĩ độ (lat) không được để trống")
    private Double lat;

    private Integer maxMotorbikes;

    private ListingCostDTO listingCosts;
}
