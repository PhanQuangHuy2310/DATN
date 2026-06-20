package com.example.timtro.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * Cấu hình tích hợp MoMo (đọc từ biến môi trường / application.yml).
 * Sử dụng luồng Gateway "captureWallet": gọi API create để lấy payUrl/QR cho người dùng thanh toán.
 */
@Component
@ConfigurationProperties(prefix = "momo")
@Data
public class MomoProperties {
    /** Mã đối tác do MoMo cấp. */
    private String partnerCode;
    /** Access key do MoMo cấp. */
    private String accessKey;
    /** Secret key dùng để ký HMAC-SHA256. */
    private String secretKey;
    /** Endpoint create payment (sandbox: https://test-payment.momo.vn/v2/gateway/api/create). */
    private String endpoint;
    /** URL frontend nơi MoMo redirect người dùng về sau khi thanh toán. */
    private String redirectUrl;
    /** URL server nhận IPN (server-to-server) từ MoMo. */
    private String ipnUrl;
    /** Số tiền gói Premium (VND). */
    private Long premiumAmount = 10000L;
}
