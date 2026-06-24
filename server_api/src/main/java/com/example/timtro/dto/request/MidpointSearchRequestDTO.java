package com.example.timtro.dto.request;

import jakarta.validation.constraints.NotEmpty;
import lombok.Data;

import java.util.List;

@Data
public class MidpointSearchRequestDTO {
    
    @NotEmpty(message = "Danh sách tọa độ không được để trống")
    private List<CoordinateDTO> coordinates;

    private double radius = 5000; // Mặc định 5km
}
