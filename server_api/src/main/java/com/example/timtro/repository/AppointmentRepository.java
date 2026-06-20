package com.example.timtro.repository;

import com.example.timtro.entity.Appointment;
import com.example.timtro.entity.AppointmentStatus;
import com.example.timtro.entity.Listing;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.UUID;

@Repository
public interface AppointmentRepository extends JpaRepository<Appointment, UUID> {
    boolean existsByListingAndScheduledAtAndStatus(Listing listing, LocalDateTime scheduledAt, AppointmentStatus status);
}
