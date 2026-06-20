package com.example.timtro.controller;

import com.example.timtro.dto.response.StatisticProjection;
import com.example.timtro.service.StatisticService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/statistics")
@RequiredArgsConstructor
public class StatisticController {

    private final StatisticService statisticService;

    @GetMapping("/landlord/last-7-days")
    public ResponseEntity<List<StatisticProjection>> getStatistics(Authentication authentication) {
        String email = authentication.getName();
        return ResponseEntity.ok(statisticService.getStatisticsForLandlordLast7Days(email));
    }
}
