package com.example.timtro.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "user_lifestyles")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserLifestyle {

    @Id
    private UUID userId;

    @OneToOne(fetch = FetchType.LAZY)
    @MapsId
    @JoinColumn(name = "user_id")
    private User user;

    @Column(nullable = false)
    @Builder.Default
    private Integer cleanliness = 3; // 1-5

    @Column(nullable = false)
    @Builder.Default
    private Integer extroversion = 3; // 1-5

    @Column(name = "early_bird", nullable = false)
    @Builder.Default
    private Integer earlyBird = 3; // 1-5 (1: Night Owl, 5: Early Bird)

    @Column(nullable = false)
    @Builder.Default
    private Integer cooking = 3; // 1-5

    @Column(name = "guest_tolerance", nullable = false)
    @Builder.Default
    private Integer guestTolerance = 3; // 1-5

    @UpdateTimestamp
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;
}
