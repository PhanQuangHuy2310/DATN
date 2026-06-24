package com.example.timtro.dto.response;

import com.example.timtro.entity.Role;
import com.example.timtro.entity.UserStatus;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserAdminDTO {
    private UUID id;
    private String fullName;
    private String email;
    private Role role;
    private UserStatus status;
    private String avatarUrl;
    private long postCount;
}
