package com.example.timtro.dto.response;

import com.example.timtro.entity.Role;
import com.example.timtro.entity.UserStatus;
import lombok.Builder;
import lombok.Data;

import java.util.UUID;
import java.time.LocalDateTime;

@Data
@Builder
public class UserProfileDTO {
    private UUID id;
    private String email;
    private String fullName;
    private String phone;
    private String avatarUrl;
    private Role role;
    private UserStatus status;
    private Boolean verified;
    private LocalDateTime premiumExpiryDate;
}
