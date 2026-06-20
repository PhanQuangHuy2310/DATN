package com.example.timtro.controller;

import com.example.timtro.dto.response.PaymentInitResponse;
import com.example.timtro.entity.User;
import com.example.timtro.repository.UserRepository;
import com.example.timtro.service.MomoPaymentService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/payment")
@RequiredArgsConstructor
public class PaymentController {

    private final MomoPaymentService momoPaymentService;
    private final UserRepository userRepository;

    /**
     * Khởi tạo thanh toán MoMo để gia hạn gói Premium 30 ngày.
     * Trả về payUrl/qrCodeUrl để frontend redirect hoặc hiển thị QR cho người dùng thanh toán.
     */
    @PostMapping("/momo/create-premium")
    @PreAuthorize("hasRole('LANDLORD')")
    public ResponseEntity<PaymentInitResponse> createPremiumPayment(Authentication authentication) {
        String email = authentication.getName();
        User currentUser = userRepository.findByEmail(email)
                .orElseThrow(() -> new IllegalArgumentException("User không tồn tại"));

        return ResponseEntity.ok(momoPaymentService.createPremiumPayment(currentUser));
    }
}
