package com.example.timtro.repository;

import com.example.timtro.dto.response.StatisticProjection;
import com.example.timtro.entity.ViewEvent;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.UUID;

public interface ViewEventRepository extends JpaRepository<ViewEvent, UUID> {

    @Query(value = """
            SELECT 
                CAST(v.created_at AS DATE) as date,
                SUM(CASE WHEN v.event_type = 'VIEW' THEN 1 ELSE 0 END) as totalViews,
                SUM(CASE WHEN v.event_type = 'CONTACT_CLICK' THEN 1 ELSE 0 END) as totalClicks
            FROM view_events v
            JOIN listings l ON v.listing_id = l.id
            WHERE l.landlord_id = :landlordId 
              AND v.created_at >= CURRENT_DATE - INTERVAL '6 days'
            GROUP BY CAST(v.created_at AS DATE)
            ORDER BY CAST(v.created_at AS DATE)
            """, nativeQuery = true)
    List<StatisticProjection> getStatisticsForLandlordLast7Days(@Param("landlordId") UUID landlordId);
}
