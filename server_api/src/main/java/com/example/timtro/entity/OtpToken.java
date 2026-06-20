package com.example.timtro.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

import java.util.UUID;

@Entity
@Table(name = "otp_tokens")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class OtpToken {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(name = "otp_code", nullable = false, length = 6)
    private String otpCode;

    @Column(name = "expiry_time", nullable = false)
    private LocalDateTime expiryTime;
}
