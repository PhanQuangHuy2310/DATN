package com.example.timtro.controller;

import com.example.timtro.dto.request.LoginRequestDTO;
import com.example.timtro.dto.request.RegisterRequest;
import com.example.timtro.dto.response.LoginResponseDTO;
import com.example.timtro.dto.response.MessageResponse;
import com.example.timtro.service.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/register")
    public ResponseEntity<MessageResponse> register(@Valid @RequestBody RegisterRequest request) {
        MessageResponse response = authService.register(request);
        return ResponseEntity.ok(response);
    }

    @PostMapping("/login")
    public ResponseEntity<LoginResponseDTO> login(@Valid @RequestBody LoginRequestDTO request) {
        return ResponseEntity.ok(authService.login(request));
    }

    @PostMapping("/verify-otp")
    public ResponseEntity<LoginResponseDTO> verifyOtp(@Valid @RequestBody com.example.timtro.dto.request.VerifyOtpRequestDTO request) {
        return ResponseEntity.ok(authService.verifyOtp(request));
    }

    @PostMapping("/resend-otp")
    public ResponseEntity<MessageResponse> resendOtp(@Valid @RequestBody com.example.timtro.dto.request.ResendOtpRequestDTO request) {
        return ResponseEntity.ok(authService.resendOtp(request));
    }

    @PostMapping("/refresh")
    public ResponseEntity<LoginResponseDTO> refreshToken(@Valid @RequestBody com.example.timtro.dto.request.RefreshTokenRequestDTO request) {
        return ResponseEntity.ok(authService.refreshToken(request));
    }

    @PostMapping("/logout")
    public ResponseEntity<MessageResponse> logout(@Valid @RequestBody com.example.timtro.dto.request.LogoutRequestDTO request) {
        authService.logout(request);
        return ResponseEntity.ok(new MessageResponse("Đăng xuất thành công"));
    }
}
