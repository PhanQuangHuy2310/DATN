package com.example.timtro.scheduler;

import com.example.timtro.entity.Listing;
import com.example.timtro.entity.ListingStatus;
import com.example.timtro.entity.User;
import com.example.timtro.repository.ListingRepository;
import com.example.timtro.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Component
@RequiredArgsConstructor
@Slf4j
public class SubscriptionCleanupScheduler {

    private final UserRepository userRepository;
    private final ListingRepository listingRepository;

    // Chạy lúc 1:00 sáng mỗi ngày
    @Scheduled(cron = "0 0 1 * * ?")
    @Transactional
    public void hideListingsForExpiredSubscriptions() {
        log.info("Bắt đầu quét các Landlord hết hạn Premium...");
        
        // Lấy tất cả user (Để tối ưu thì nên query trực tiếp các user có premiumExpiryDate < now)
        // Tuy nhiên trong demo, ta lấy toàn bộ hoặc có thể dùng phương thức custom.
        // Giả sử lấy toàn bộ, hoặc viết query (ở đây viết logic trên java cho nhanh nếu DB nhỏ):
        List<User> users = userRepository.findAll(); 

        for (User user : users) {
            if (user.getPremiumExpiryDate() != null && user.getPremiumExpiryDate().isBefore(LocalDateTime.now())) {
                
                // Lấy danh sách listing của user này (đã sắp xếp cũ nhất -> mới nhất)
                List<Listing> userListings = listingRepository.findByUserOrderByCreatedAtAsc(user);
                
                // Đếm số lượng active (không tính HIDDEN)
                long activeCount = userListings.stream()
                        .filter(l -> l.getStatus() != ListingStatus.HIDDEN)
                        .count();

                if (activeCount > 5) {
                    log.info("User {} đã hết hạn Premium và đang có {} active listings. Sẽ ẩn các tin thừa...", user.getEmail(), activeCount);
                    
                    // Giữ lại 5 tin đầu tiên không bị HIDDEN, còn lại ẩn hết
                    int keepCount = 0;
                    for (Listing listing : userListings) {
                        if (listing.getStatus() != ListingStatus.HIDDEN) {
                            keepCount++;
                            if (keepCount > 5) {
                                listing.setStatus(ListingStatus.HIDDEN);
                                listingRepository.save(listing);
                            }
                        }
                    }
                }
            }
        }
        
        log.info("Quét hết hạn Premium hoàn tất.");
    }
}
