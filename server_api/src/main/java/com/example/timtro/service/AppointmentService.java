package com.example.timtro.service;

import com.example.timtro.dto.request.AppointmentCreateRequest;
import com.example.timtro.entity.Appointment;
import com.example.timtro.entity.AppointmentStatus;
import com.example.timtro.entity.Listing;
import com.example.timtro.entity.User;
import com.example.timtro.repository.AppointmentRepository;
import com.example.timtro.repository.ListingRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class AppointmentService {

    private final AppointmentRepository appointmentRepository;
    private final ListingRepository listingRepository;

    @Transactional
    public UUID bookAppointment(AppointmentCreateRequest request, User tenant) {
        Listing listing = listingRepository.findById(request.getListingId())
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy phòng trọ"));

        // Chống Double Booking
        boolean isDoubleBooked = appointmentRepository.existsByListingAndScheduledAtAndStatus(
                listing, request.getScheduledAt(), AppointmentStatus.CONFIRMED);

        if (isDoubleBooked) {
            throw new IllegalStateException("Khung giờ này đã được đặt và xác nhận bởi người khác.");
        }

        Appointment appointment = Appointment.builder()
                .listing(listing)
                .tenant(tenant)
                .scheduledAt(request.getScheduledAt())
                .status(AppointmentStatus.PENDING)
                .note(request.getNote())
                .build();

        appointment = appointmentRepository.save(appointment);
        return appointment.getId();
    }
    @Transactional
    public void changeAppointmentStatus(UUID appointmentId, AppointmentStatus newStatus, String userEmail) {
        Appointment appointment = appointmentRepository.findById(appointmentId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy lịch hẹn"));

        if (!appointment.getListing().getUser().getEmail().equals(userEmail)) {
            throw new IllegalArgumentException("Bạn không có quyền duyệt lịch hẹn này");
        }

        appointment.setStatus(newStatus);
        appointmentRepository.save(appointment);
    }
}
