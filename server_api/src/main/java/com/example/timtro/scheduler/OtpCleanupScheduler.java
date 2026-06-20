package com.example.timtro.scheduler;

import com.example.timtro.repository.OtpTokenRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Component
@RequiredArgsConstructor
@Slf4j
public class OtpCleanupScheduler {

    private final OtpTokenRepository otpTokenRepository;

    // Chạy vào 2:00 sáng mỗi ngày
    @Scheduled(cron = "0 0 2 * * ?")
    @Transactional
    public void cleanupExpiredOtps() {
        log.info("Bắt đầu dọn dẹp các mã OTP đã hết hạn trên 7 ngày...");
        // Lấy thời điểm hiện tại trừ đi 7 ngày
        LocalDateTime threshold = LocalDateTime.now().minusDays(7);
        
        try {
            otpTokenRepository.deleteByExpiryTimeBefore(threshold);
            log.info("Hoàn tất dọn dẹp OTP cũ (trước {}).", threshold);
        } catch (Exception e) {
            log.error("Lỗi khi dọn dẹp OTP: {}", e.getMessage());
        }
    }
}
