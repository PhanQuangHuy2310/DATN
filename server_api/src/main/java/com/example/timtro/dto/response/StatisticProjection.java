package com.example.timtro.dto.response;

import java.time.LocalDate;

public interface StatisticProjection {
    LocalDate getDate();
    Long getTotalViews();
    Long getTotalClicks();
}
