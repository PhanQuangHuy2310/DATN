package com.example.timtro.dto.response;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

/**
 * Phản hồi từ API create của MoMo.
 */
@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class MomoCreateResponse {
    private String partnerCode;
    private String orderId;
    private String requestId;
    private Long amount;
    private Long responseTime;
    private String message;
    private Integer resultCode;
    private String payUrl;
    private String deeplink;
    private String qrCodeUrl;
}
