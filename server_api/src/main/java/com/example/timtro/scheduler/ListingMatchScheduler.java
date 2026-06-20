package com.example.timtro.scheduler;

import com.example.timtro.entity.Listing;
import com.example.timtro.entity.ListingStatus;
import com.example.timtro.entity.SavedSearch;
import com.example.timtro.repository.ListingRepository;
import com.example.timtro.repository.SavedSearchRepository;
import com.example.timtro.service.NotificationService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Component
@RequiredArgsConstructor
@Slf4j
public class ListingMatchScheduler {

    private final ListingRepository listingRepository;
    private final SavedSearchRepository savedSearchRepository;
    private final NotificationService notificationService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    // Chạy mỗi 30 phút (1800000 ms)
    @Scheduled(fixedDelay = 1800000)
    @Transactional(readOnly = true)
    public void checkAndNotifyMatchingListings() {
        log.info("Bắt đầu job quét tin đăng mới phù hợp với người dùng...");

        LocalDateTime thirtyMinutesAgo = LocalDateTime.now().minusMinutes(30);

        // Lấy danh sách phòng trọ vừa được đăng trong vòng 30 phút (giả định chưa có ListingSpecification, dùng stream tạm thời)
        // Trong thực tế nên viết query: findByStatusAndCreatedAtAfter
        List<Listing> newAvailableListings = listingRepository.findAll().stream()
                .filter(l -> l.getStatus() == ListingStatus.APPROVED || l.getStatus() == ListingStatus.PENDING)
                .filter(l -> l.getCreatedAt() != null && l.getCreatedAt().isAfter(thirtyMinutesAgo))
                .toList();

        if (newAvailableListings.isEmpty()) {
            log.info("Không có tin đăng mới trong 30 phút qua.");
            return;
        }

        List<SavedSearch> activeSearches = savedSearchRepository.findByIsActiveTrue();

        for (SavedSearch search : activeSearches) {
            try {
                // Parse chuỗi JSON filter (VD: {"minPrice": 1000000, "maxPrice": 3000000, "minArea": 15})
                Map<String, Object> filters = objectMapper.readValue(search.getFilterJson(), new TypeReference<>() {});

                Double minPrice = filters.containsKey("minPrice") ? Double.valueOf(filters.get("minPrice").toString()) : null;
                Double maxPrice = filters.containsKey("maxPrice") ? Double.valueOf(filters.get("maxPrice").toString()) : null;
                Double minArea = filters.containsKey("minArea") ? Double.valueOf(filters.get("minArea").toString()) : null;

                for (Listing listing : newAvailableListings) {
                    boolean isMatch = true;

                    if (minPrice != null && listing.getPrice() < minPrice) isMatch = false;
                    if (maxPrice != null && listing.getPrice() > maxPrice) isMatch = false;
                    if (minArea != null && listing.getArea() < minArea) isMatch = false;

                    if (isMatch) {
                        notificationService.sendAlert(search.getUser().getId(), listing.getId());
                    }
                }
            } catch (Exception e) {
                log.error("Lỗi khi parse filter JSON cho user {}", search.getUser().getId(), e);
            }
        }
        
        log.info("Hoàn tất job quét tin đăng mới.");
    }
}
