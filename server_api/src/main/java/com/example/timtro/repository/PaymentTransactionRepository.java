package com.example.timtro.repository;

import com.example.timtro.entity.PaymentTransaction;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;
import java.util.UUID;

public interface PaymentTransactionRepository extends JpaRepository<PaymentTransaction, UUID> {
    Optional<PaymentTransaction> findByOrderId(String orderId);
}
