package com.example.timtro.dto.response;

import lombok.AllArgsConstructor;
import lombok.Data;

/**
 * Phản hồi trả về cho frontend sau khi khởi tạo thanh toán MoMo thành công.
 */
@Data
@AllArgsConstructor
public class PaymentInitResponse {
    private String orderId;
    private String payUrl;
    private String deeplink;
    private String qrCodeUrl;
}
