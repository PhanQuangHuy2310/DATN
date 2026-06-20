package com.example.timtro.service;

import com.example.timtro.dto.response.StatisticProjection;
import com.example.timtro.entity.User;
import com.example.timtro.repository.UserRepository;
import com.example.timtro.repository.ViewEventRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class StatisticService {

    private final ViewEventRepository viewEventRepository;
    private final UserRepository userRepository;

    @Transactional(readOnly = true)
    public List<StatisticProjection> getStatisticsForLandlordLast7Days(String email) {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new RuntimeException("User not found"));
        return viewEventRepository.getStatisticsForLandlordLast7Days(user.getId());
    }
}
