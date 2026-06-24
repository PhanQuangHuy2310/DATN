package com.example.timtro.repository;

import com.example.timtro.entity.OtpToken;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;

import java.util.UUID;

@Repository
public interface OtpTokenRepository extends JpaRepository<OtpToken, UUID> {
    java.util.Optional<OtpToken> findTopByUserOrderByExpiryTimeDesc(com.example.timtro.entity.User user);

    @Modifying
    @Query("DELETE FROM OtpToken o WHERE o.expiryTime < :time")
    void deleteByExpiryTimeBefore(LocalDateTime time);
}
