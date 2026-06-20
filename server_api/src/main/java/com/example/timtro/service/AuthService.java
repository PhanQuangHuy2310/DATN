package com.example.timtro.service;

import com.example.timtro.dto.request.RegisterRequest;
import com.example.timtro.dto.response.MessageResponse;
import com.example.timtro.entity.Role;
import com.example.timtro.entity.User;
import com.example.timtro.entity.UserStatus;
import com.example.timtro.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import com.example.timtro.security.JwtTokenProvider;
import com.example.timtro.dto.request.LoginRequestDTO;
import com.example.timtro.dto.response.LoginResponseDTO;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final EmailOtpService emailOtpService;
    private final AuthenticationManager authenticationManager;
    private final JwtTokenProvider jwtTokenProvider;

    @Transactional
    public MessageResponse register(RegisterRequest request) {
        if (userRepository.existsByEmail(request.getEmail())) {
            throw new IllegalArgumentException("Email đã tồn tại trong hệ thống");
        }

        User user = User.builder()
                .email(request.getEmail())
                .password(passwordEncoder.encode(request.getPassword()))
                .fullName(request.getFullName())
                .role(request.getRole())
                .build();

        if (request.getRole() == Role.TENANT) {
            user.setStatus(UserStatus.ACTIVE);
            userRepository.save(user);
            return new MessageResponse("Đăng ký thành công (TENANT)");
        } else if (request.getRole() == Role.LANDLORD) {
            user.setStatus(UserStatus.INACTIVE);
            user = userRepository.save(user);
            
            // Generate and send OTP for LANDLORD
            emailOtpService.generateAndSendOtp(user);
            
            return new MessageResponse("Đăng ký thành công (LANDLORD). Vui lòng kiểm tra email để nhận mã OTP kích hoạt tài khoản.");
        } else {
            throw new IllegalArgumentException("Role không hợp lệ");
        }
    }

    @Transactional(readOnly = true)
    public LoginResponseDTO login(LoginRequestDTO request) {
        Authentication authentication = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(
                        request.getEmail(),
                        request.getPassword()
                )
        );

        SecurityContextHolder.getContext().setAuthentication(authentication);

        String accessToken = jwtTokenProvider.generateAccessToken(authentication);
        String refreshToken = jwtTokenProvider.generateRefreshToken(authentication);

        User user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> new IllegalArgumentException("Người dùng không tồn tại"));

        if (user.getStatus() != UserStatus.ACTIVE) {
            throw new IllegalArgumentException("Tài khoản chưa được kích hoạt hoặc bị khóa");
        }

        return LoginResponseDTO.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .userId(user.getId())
                .email(user.getEmail())
                .role(user.getRole().name())
                .build();
    }
}
