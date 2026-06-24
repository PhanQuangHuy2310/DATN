package com.example.timtro.repository;

import com.example.timtro.entity.User;
import com.example.timtro.entity.Role;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface UserRepository extends JpaRepository<User, UUID> {
    @Query("SELECT u FROM User u WHERE u.email = :emailOrId OR CAST(u.id AS string) = :emailOrId")
    Optional<User> findByEmail(@Param("emailOrId") String emailOrId);
    
    boolean existsByEmail(String email);
    
    Optional<User> findByEmailAndRole(String email, Role role);
    boolean existsByEmailAndRole(String email, Role role);
    boolean existsByPhoneAndRole(String phone, Role role);
}

