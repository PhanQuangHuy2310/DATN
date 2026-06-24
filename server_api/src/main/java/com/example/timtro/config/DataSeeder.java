package com.example.timtro.config;

import com.example.timtro.entity.Role;
import com.example.timtro.entity.User;
import com.example.timtro.entity.UserStatus;
import com.example.timtro.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.util.Optional;

@Component
@RequiredArgsConstructor
public class DataSeeder implements CommandLineRunner {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Override
    public void run(String... args) throws Exception {
        Optional<User> adminUser = userRepository.findByEmail("admin@timtro.com");
        if (adminUser.isEmpty()) {
            User admin = User.builder()
                    .email("admin@timtro.com")
                    .password(passwordEncoder.encode("admin123"))
                    .fullName("Quản trị viên")
                    .role(Role.ADMIN)
                    .status(UserStatus.ACTIVE)
                    .verified(true)
                    .build();
            userRepository.save(admin);
            System.out.println("====== ĐÃ TẠO TÀI KHOẢN ADMIN MẶC ĐỊNH ======");
            System.out.println("Email: admin@timtro.com");
            System.out.println("Pass: admin123");
            System.out.println("===========================================");
        }
    }
}
