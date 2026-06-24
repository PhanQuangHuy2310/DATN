package com.example.timtro.service;

import com.example.timtro.entity.OtpToken;
import com.example.timtro.entity.User;
import com.example.timtro.repository.OtpTokenRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
@Slf4j
public class EmailOtpService {

    private final OtpTokenRepository otpTokenRepository;
    private final JavaMailSender mailSender;

    private static final String CHARACTERS = "0123456789";
    private static final int OTP_LENGTH = 6;
    private static final int OTP_VALID_DURATION_MINUTES = 5;

    @Transactional
    public void generateAndSendOtp(User user) {
        String otpCode = generateOtp();

        OtpToken otpToken = OtpToken.builder()
                .user(user)
                .otpCode(otpCode)
                .expiryTime(LocalDateTime.now().plusMinutes(OTP_VALID_DURATION_MINUTES))
                .build();

        otpTokenRepository.save(otpToken);

        log.info("=== DEV MODE: Mã OTP của {} là: {} ===", user.getEmail(), otpCode);
        
        sendOtpEmail(user.getEmail(), otpCode);
    }

    private String generateOtp() {
        SecureRandom random = new SecureRandom();
        StringBuilder sb = new StringBuilder(OTP_LENGTH);
        for (int i = 0; i < OTP_LENGTH; i++) {
            sb.append(CHARACTERS.charAt(random.nextInt(CHARACTERS.length())));
        }
        return sb.toString();
    }

    private void sendOtpEmail(String toEmail, String otpCode) {
        try {
            SimpleMailMessage message = new SimpleMailMessage();
            message.setTo(toEmail);
            message.setSubject("Mã xác thực OTP - Nền tảng tìm phòng trọ");
            message.setText("Mã xác thực OTP của bạn là: " + otpCode + "\nMã này có hiệu lực trong " + OTP_VALID_DURATION_MINUTES + " phút.");

            mailSender.send(message);
            log.info("OTP sent to email: {}", toEmail);
        } catch (Exception e) {
            log.error("Failed to send OTP email to {}: {}", toEmail, e.getMessage());
            // Tuỳ chọn: Có thể throw exception nếu muốn báo lỗi cho user khi không gửi được email
            // throw new RuntimeException("Lỗi khi gửi email", e);
        }
    }
}
