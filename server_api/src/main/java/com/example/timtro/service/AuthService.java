package com.example.timtro.service;

import com.example.timtro.dto.request.RegisterRequest;
import com.example.timtro.dto.response.MessageResponse;
import com.example.timtro.entity.Role;
import com.example.timtro.entity.User;
import com.example.timtro.entity.UserStatus;
import com.example.timtro.entity.OtpToken;
import com.example.timtro.repository.UserRepository;
import com.example.timtro.repository.OtpTokenRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import com.example.timtro.security.JwtTokenProvider;
import com.example.timtro.dto.request.LoginRequestDTO;
import com.example.timtro.dto.request.VerifyOtpRequestDTO;
import com.example.timtro.dto.request.ResendOtpRequestDTO;
import com.example.timtro.dto.request.RefreshTokenRequestDTO;
import com.example.timtro.dto.response.LoginResponseDTO;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final OtpTokenRepository otpTokenRepository;
    private final PasswordEncoder passwordEncoder;
    private final EmailOtpService emailOtpService;
    private final AuthenticationManager authenticationManager;
    private final JwtTokenProvider jwtTokenProvider;
    private final com.example.timtro.repository.InvalidatedTokenRepository invalidatedTokenRepository;

    @Transactional
    public MessageResponse register(RegisterRequest request) {
        if (userRepository.existsByEmailAndRole(request.getEmail(), request.getRole())) {
            throw new IllegalArgumentException("Email đã tồn tại cho vai trò này");
        }
        if (request.getPhone() != null && !request.getPhone().trim().isEmpty() &&
                userRepository.existsByPhoneAndRole(request.getPhone(), request.getRole())) {
            throw new IllegalArgumentException("Số điện thoại đã tồn tại cho vai trò này");
        }

        User user = User.builder()
                .email(request.getEmail())
                .password(passwordEncoder.encode(request.getPassword()))
                .fullName(request.getFullName())
                .phone(request.getPhone())
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
        User user = userRepository.findByEmailAndRole(request.getEmail(), request.getRole())
                .orElseThrow(() -> new IllegalArgumentException("Người dùng không tồn tại cho vai trò này"));

        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new IllegalArgumentException("Thông tin đăng nhập không chính xác");
        }

        String accessToken = jwtTokenProvider.generateToken(user);
        String refreshToken = jwtTokenProvider.generateRefreshToken(user);

        if (user.getStatus() != UserStatus.ACTIVE) {
            throw new IllegalArgumentException("Tài khoản chưa được kích hoạt hoặc bị khóa");
        }

        return LoginResponseDTO.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .userId(user.getId())
                .email(user.getEmail())
                .role(user.getRole().name())
                .fullName(user.getFullName())
                .phone(user.getPhone())
                .avatarUrl(user.getAvatarUrl())
                .build();
    }

    @Transactional
    public LoginResponseDTO verifyOtp(VerifyOtpRequestDTO request) {
        User user = userRepository.findByEmailAndRole(request.getEmail(), Role.LANDLORD)
                .orElseThrow(() -> new IllegalArgumentException("Người dùng không tồn tại hoặc vai trò không hợp lệ"));

        if (user.getStatus() == UserStatus.ACTIVE) {
            throw new IllegalArgumentException("Tài khoản đã được kích hoạt");
        }

        OtpToken otpToken = otpTokenRepository.findTopByUserOrderByExpiryTimeDesc(user)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy mã OTP cho người dùng này"));

        if (otpToken.getExpiryTime().isBefore(LocalDateTime.now())) {
            throw new IllegalArgumentException("Mã OTP đã hết hạn");
        }

        if (!otpToken.getOtpCode().equals(request.getOtpCode())) {
            throw new IllegalArgumentException("Mã OTP không chính xác");
        }

        // Active user
        user.setStatus(UserStatus.ACTIVE);
        userRepository.save(user);
        
        // Delete OTP token
        otpTokenRepository.delete(otpToken);

        // Generate tokens
        String accessToken = jwtTokenProvider.generateToken(user);
        String refreshToken = jwtTokenProvider.generateRefreshToken(user);

        return LoginResponseDTO.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .userId(user.getId())
                .email(user.getEmail())
                .role(user.getRole().name())
                .fullName(user.getFullName())
                .phone(user.getPhone())
                .avatarUrl(user.getAvatarUrl())
                .build();
    }

    @Transactional
    public MessageResponse resendOtp(ResendOtpRequestDTO request) {
        User user = userRepository.findByEmailAndRole(request.getEmail(), Role.LANDLORD)
                .orElseThrow(() -> new IllegalArgumentException("Người dùng không tồn tại hoặc vai trò không hợp lệ"));

        if (user.getStatus() == UserStatus.ACTIVE) {
            throw new IllegalArgumentException("Tài khoản đã được kích hoạt");
        }

        emailOtpService.generateAndSendOtp(user);
        return new MessageResponse("Đã gửi lại mã OTP. Vui lòng kiểm tra email.");
    }

    @Transactional(readOnly = true)
    public LoginResponseDTO refreshToken(RefreshTokenRequestDTO request) {
        String requestRefreshToken = request.getRefreshToken();

        try {
            com.nimbusds.jwt.SignedJWT signedJWT = jwtTokenProvider.verifyToken(requestRefreshToken);
            String userIdStr = signedJWT.getJWTClaimsSet().getSubject();

            User user = userRepository.findById(java.util.UUID.fromString(userIdStr))
                    .orElseThrow(() -> new IllegalArgumentException("Người dùng không tồn tại"));

            if (user.getStatus() != UserStatus.ACTIVE) {
                throw new IllegalArgumentException("Tài khoản chưa được kích hoạt hoặc bị khóa");
            }

            // Invalidate the old refresh token
            String jti = signedJWT.getJWTClaimsSet().getJWTID();
            java.util.Date expiryTime = signedJWT.getJWTClaimsSet().getExpirationTime();
            invalidatedTokenRepository.save(new com.example.timtro.entity.InvalidatedToken(jti, expiryTime));

            String accessToken = jwtTokenProvider.generateToken(user);
            String newRefreshToken = jwtTokenProvider.generateRefreshToken(user);

            return LoginResponseDTO.builder()
                    .accessToken(accessToken)
                    .refreshToken(newRefreshToken)
                    .userId(user.getId())
                    .email(user.getEmail())
                    .role(user.getRole().name())
                    .fullName(user.getFullName())
                    .phone(user.getPhone())
                    .avatarUrl(user.getAvatarUrl())
                    .build();
        } catch (Exception e) {
            throw new IllegalArgumentException("Refresh token không hợp lệ hoặc đã hết hạn", e);
        }
    }

    @Transactional
    public void logout(com.example.timtro.dto.request.LogoutRequestDTO request) {
        try {
            com.nimbusds.jwt.SignedJWT signedJWT = jwtTokenProvider.verifyToken(request.getToken());
            String jti = signedJWT.getJWTClaimsSet().getJWTID();
            java.util.Date expiryTime = signedJWT.getJWTClaimsSet().getExpirationTime();
            invalidatedTokenRepository.save(new com.example.timtro.entity.InvalidatedToken(jti, expiryTime));
        } catch (Exception e) {
            // Ignore invalid tokens on logout
        }
    }
}
