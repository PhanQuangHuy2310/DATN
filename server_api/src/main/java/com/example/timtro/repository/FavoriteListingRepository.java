package com.example.timtro.repository;

import com.example.timtro.entity.FavoriteListing;
import com.example.timtro.entity.User;
import com.example.timtro.entity.Listing;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface FavoriteListingRepository extends JpaRepository<FavoriteListing, UUID> {
    Page<FavoriteListing> findByUserOrderByCreatedAtDesc(User user, Pageable pageable);
    Optional<FavoriteListing> findByUserAndListing(User user, Listing listing);
    boolean existsByUserAndListing(User user, Listing listing);
}
