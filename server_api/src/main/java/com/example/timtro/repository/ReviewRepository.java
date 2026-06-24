package com.example.timtro.repository;

import com.example.timtro.entity.Review;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.UUID;

public interface ReviewRepository extends JpaRepository<Review, UUID> {
    Page<Review> findByListingIdOrderByCreatedAtDesc(UUID listingId, Pageable pageable);

    @Query("SELECT AVG(r.rating) FROM Review r WHERE r.listing.user.id = :landlordId")
    Double getAverageRatingForLandlord(@Param("landlordId") UUID landlordId);
    
    boolean existsByListingIdAndTenantId(UUID listingId, UUID tenantId);
}
