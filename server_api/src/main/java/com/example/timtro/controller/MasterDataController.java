package com.example.timtro.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/master-data")
public class MasterDataController {

    @GetMapping("/amenities")
    public ResponseEntity<List<Map<String, String>>> getAmenities() {
        return ResponseEntity.ok(List.of(
                Map.of("id", "WIFI", "name", "Wifi tốc độ cao", "icon", "fa-wifi"),
                Map.of("id", "AC", "name", "Điều hòa", "icon", "fa-snowflake"),
                Map.of("id", "WM", "name", "Máy giặt", "icon", "fa-tshirt"),
                Map.of("id", "FRIDGE", "name", "Tủ lạnh", "icon", "fa-ice-cream"),
                Map.of("id", "PARKING", "name", "Chỗ để xe", "icon", "fa-parking"),
                Map.of("id", "SECURITY", "name", "Bảo vệ 24/7", "icon", "fa-shield-alt")
        ));
    }

    @GetMapping("/property-types")
    public ResponseEntity<List<Map<String, String>>> getPropertyTypes() {
        return ResponseEntity.ok(List.of(
                Map.of("id", "PHONG_TRO", "name", "Phòng trọ"),
                Map.of("id", "CHUNG_CU_MINI", "name", "Chung cư mini"),
                Map.of("id", "NHA_NGUYEN_CAN", "name", "Nhà nguyên căn"),
                Map.of("id", "SLEEPBOX", "name", "Sleepbox")
        ));
    }

    @GetMapping("/alley-types")
    public ResponseEntity<List<Map<String, String>>> getAlleyTypes() {
        return ResponseEntity.ok(List.of(
                Map.of("id", "NGO_RONG", "name", "Ngõ rộng (Ô tô vào được)"),
                Map.of("id", "NGO_NHO", "name", "Ngõ nhỏ (Chỉ xe máy)"),
                Map.of("id", "MAT_DUONG", "name", "Mặt đường chính")
        ));
    }
}
