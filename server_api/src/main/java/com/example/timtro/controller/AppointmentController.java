package com.example.timtro.controller;

import com.example.timtro.dto.request.AppointmentCreateRequest;
import com.example.timtro.dto.response.MessageResponse;
import com.example.timtro.entity.User;
import com.example.timtro.repository.UserRepository;
import com.example.timtro.service.AppointmentService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/api/appointments")
@RequiredArgsConstructor
public class AppointmentController {

    private final AppointmentService appointmentService;
    private final UserRepository userRepository;

    @PostMapping
    @PreAuthorize("hasRole('TENANT')")
    public ResponseEntity<MessageResponse> bookAppointment(
            @Valid @RequestBody AppointmentCreateRequest request,
            Authentication authentication) {
        
        String email = authentication.getName();
        User currentTenant = userRepository.findByEmail(email)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy người dùng"));

        UUID appointmentId = appointmentService.bookAppointment(request, currentTenant);
        
        return ResponseEntity.ok(new MessageResponse("Đặt lịch thành công. ID: " + appointmentId));
    }
}
