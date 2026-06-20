package com.example.timtro.repository;

import com.example.timtro.entity.SavedSearch;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface SavedSearchRepository extends JpaRepository<SavedSearch, UUID> {
    List<SavedSearch> findByIsActiveTrue();
}
