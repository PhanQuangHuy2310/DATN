package com.example.timtro.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.UUID;

@Service
@Slf4j
public class NotificationService {

    public void sendAlert(UUID userId, UUID listingId) {
        // Tương lai: Tích hợp Firebase Cloud Messaging (FCM) hoặc gửi qua WebSocket
        log.info("🔔 [NOTIFICATION] Gửi thông báo tới User {}: Có tin đăng mới ({}) phù hợp với tiêu chí tìm kiếm của bạn!", userId, listingId);
    }
}
