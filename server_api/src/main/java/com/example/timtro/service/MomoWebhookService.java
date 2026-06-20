package com.example.timtro.service;

import com.example.timtro.config.MomoProperties;
import com.example.timtro.dto.request.MomoCallbackDTO;
import com.example.timtro.entity.PaymentTransaction;
import com.example.timtro.entity.TransactionStatus;
import com.example.timtro.entity.User;
import com.example.timtro.repository.PaymentTransactionRepository;
import com.example.timtro.repository.UserRepository;
import com.example.timtro.util.MomoSignatureUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
@Slf4j
public class MomoWebhookService {

    private final PaymentTransactionRepository paymentTransactionRepository;
    private final UserRepository userRepository;
    private final MomoProperties momo;

    @Transactional
    public void processMomoCallback(MomoCallbackDTO callbackDTO) {
        log.info("Nhận MoMo IPN cho orderId: {}", callbackDTO.getOrderId());

        // 1. Xác thực chữ ký để chống giả mạo callback
        if (!isValidSignature(callbackDTO)) {
            log.warn("Chữ ký MoMo IPN không hợp lệ cho orderId: {}", callbackDTO.getOrderId());
            throw new SecurityException("Chữ ký MoMo không hợp lệ");
        }

        PaymentTransaction transaction = paymentTransactionRepository.findByOrderId(callbackDTO.getOrderId())
                .orElseThrow(() -> new RuntimeException("Transaction not found"));

        // 2. Idempotent: bỏ qua nếu đã xử lý thành công
        if (transaction.getStatus() == TransactionStatus.SUCCESS) {
            log.info("Giao dịch đã được xử lý trước đó: {}", callbackDTO.getOrderId());
            return;
        }

        if (callbackDTO.getResultCode() != null && callbackDTO.getResultCode() == 0) {
            transaction.setStatus(TransactionStatus.SUCCESS);
            transaction.setTransId(callbackDTO.getTransId() != null ? callbackDTO.getTransId().toString() : null);
            paymentTransactionRepository.save(transaction);

            // 3. Gia hạn Premium 30 ngày trên chính cơ chế mà app sử dụng (User.premiumExpiryDate)
            User user = transaction.getUser();
            LocalDateTime now = LocalDateTime.now();
            LocalDateTime base = (user.getPremiumExpiryDate() != null && user.getPremiumExpiryDate().isAfter(now))
                    ? user.getPremiumExpiryDate()
                    : now;
            user.setPremiumExpiryDate(base.plusDays(30));
            userRepository.save(user);

            log.info("Đã gia hạn Premium tới {} cho user: {}", user.getPremiumExpiryDate(), user.getEmail());
        } else {
            transaction.setStatus(TransactionStatus.FAILED);
            paymentTransactionRepository.save(transaction);
            log.warn("Thanh toán thất bại orderId: {}, message: {}", callbackDTO.getOrderId(), callbackDTO.getMessage());
        }
    }

    /** Tạo lại chữ ký từ dữ liệu IPN và so sánh với chữ ký MoMo gửi tới. */
    private boolean isValidSignature(MomoCallbackDTO dto) {
        if (dto.getSignature() == null) {
            return false;
        }
        String rawSignature = "accessKey=" + momo.getAccessKey()
                + "&amount=" + nullToEmpty(dto.getAmount())
                + "&extraData=" + nullToEmpty(dto.getExtraData())
                + "&message=" + nullToEmpty(dto.getMessage())
                + "&orderId=" + nullToEmpty(dto.getOrderId())
                + "&orderInfo=" + nullToEmpty(dto.getOrderInfo())
                + "&orderType=" + nullToEmpty(dto.getOrderType())
                + "&partnerCode=" + nullToEmpty(dto.getPartnerCode())
                + "&payType=" + nullToEmpty(dto.getPayType())
                + "&requestId=" + nullToEmpty(dto.getRequestId())
                + "&responseTime=" + nullToEmpty(dto.getResponseTime())
                + "&resultCode=" + nullToEmpty(dto.getResultCode())
                + "&transId=" + nullToEmpty(dto.getTransId());

        String expected = MomoSignatureUtil.sign(rawSignature, momo.getSecretKey());
        return expected.equals(dto.getSignature());
    }

    private String nullToEmpty(Object value) {
        return value == null ? "" : value.toString();
    }
}
