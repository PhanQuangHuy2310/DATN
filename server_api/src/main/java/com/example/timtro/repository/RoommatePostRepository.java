package com.example.timtro.repository;

import com.example.timtro.entity.RoommatePost;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface RoommatePostRepository extends JpaRepository<RoommatePost, UUID> {
    Page<RoommatePost> findByIsActiveTrueOrderByCreatedAtDesc(Pageable pageable);
}
