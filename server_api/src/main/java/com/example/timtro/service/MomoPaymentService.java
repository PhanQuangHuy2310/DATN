package com.example.timtro.service;

import com.example.timtro.config.MomoProperties;
import com.example.timtro.dto.response.MomoCreateResponse;
import com.example.timtro.dto.response.PaymentInitResponse;
import com.example.timtro.entity.PaymentTransaction;
import com.example.timtro.entity.TransactionStatus;
import com.example.timtro.entity.User;
import com.example.timtro.repository.PaymentTransactionRepository;
import com.example.timtro.util.MomoSignatureUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Khởi tạo thanh toán MoMo theo luồng Gateway "captureWallet":
 * tạo orderId, ký HMAC-SHA256, gọi API create để lấy payUrl/QR và lưu giao dịch ở trạng thái PENDING.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class MomoPaymentService {

    private static final String REQUEST_TYPE = "captureWallet";
    private static final String LANG = "vi";

    private final MomoProperties momo;
    private final PaymentTransactionRepository paymentTransactionRepository;

    private final RestClient restClient = RestClient.create();

    /** Khởi tạo thanh toán gia hạn gói Premium 30 ngày cho người dùng. */
    public PaymentInitResponse createPremiumPayment(User user) {
        long amount = momo.getPremiumAmount();
        String orderInfo = "Thanh toan goi Premium 30 ngay";
        // orderId/requestId phải duy nhất và khớp regex ^[0-9a-zA-Z]([-_.]*[0-9a-zA-Z]+)*$
        String orderId = "TIMTRO" + System.currentTimeMillis();
        String requestId = orderId;
        String extraData = "";

        // Chuỗi raw phải sắp xếp khóa a-z theo đúng đặc tả MoMo
        String rawSignature = "accessKey=" + momo.getAccessKey()
                + "&amount=" + amount
                + "&extraData=" + extraData
                + "&ipnUrl=" + momo.getIpnUrl()
                + "&orderId=" + orderId
                + "&orderInfo=" + orderInfo
                + "&partnerCode=" + momo.getPartnerCode()
                + "&redirectUrl=" + momo.getRedirectUrl()
                + "&requestId=" + requestId
                + "&requestType=" + REQUEST_TYPE;

        String signature = MomoSignatureUtil.sign(rawSignature, momo.getSecretKey());

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("partnerCode", momo.getPartnerCode());
        body.put("accessKey", momo.getAccessKey());
        body.put("requestId", requestId);
        body.put("amount", String.valueOf(amount));
        body.put("orderId", orderId);
        body.put("orderInfo", orderInfo);
        body.put("redirectUrl", momo.getRedirectUrl());
        body.put("ipnUrl", momo.getIpnUrl());
        body.put("extraData", extraData);
        body.put("requestType", REQUEST_TYPE);
        body.put("signature", signature);
        body.put("lang", LANG);

        MomoCreateResponse response;
        try {
            response = restClient.post()
                    .uri(momo.getEndpoint())
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(MomoCreateResponse.class);
        } catch (Exception e) {
            log.error("Lỗi gọi API create MoMo", e);
            throw new RuntimeException("Không thể kết nối tới cổng thanh toán MoMo");
        }

        if (response == null || response.getResultCode() == null || response.getResultCode() != 0) {
            String msg = response != null ? response.getMessage() : "không có phản hồi";
            log.error("MoMo create thất bại: resultCode={}, message={}",
                    response != null ? response.getResultCode() : null, msg);
            throw new RuntimeException("Khởi tạo thanh toán MoMo thất bại: " + msg);
        }

        PaymentTransaction transaction = PaymentTransaction.builder()
                .orderId(orderId)
                .amount(amount)
                .status(TransactionStatus.PENDING)
                .user(user)
                .build();
        paymentTransactionRepository.save(transaction);

        log.info("Đã khởi tạo thanh toán MoMo orderId={} cho user={}", orderId, user.getEmail());
        return new PaymentInitResponse(orderId, response.getPayUrl(), response.getDeeplink(), response.getQrCodeUrl());
    }
}
