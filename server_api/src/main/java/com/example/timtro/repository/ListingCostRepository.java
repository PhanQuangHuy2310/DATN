package com.example.timtro.repository;

import com.example.timtro.entity.ListingCost;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface ListingCostRepository extends JpaRepository<ListingCost, UUID> {
}
