package com.example.timtro.repository;

import com.example.timtro.entity.UserLifestyle;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.UUID;

public interface UserLifestyleRepository extends JpaRepository<UserLifestyle, UUID> {
}
