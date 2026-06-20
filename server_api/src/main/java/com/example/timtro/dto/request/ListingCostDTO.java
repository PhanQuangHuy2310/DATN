package com.example.timtro.dto.request;

import lombok.Data;

@Data
public class ListingCostDTO {
    private Double electricityPrice;
    private Double waterPrice;
    private Double internetPrice;
}
