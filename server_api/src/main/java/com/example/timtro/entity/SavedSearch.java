package com.example.timtro.entity;

import jakarta.persistence.*;
import lombok.*;

import java.util.UUID;

@Entity
@Table(name = "saved_searches")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class SavedSearch {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(name = "filter_json", nullable = false, columnDefinition = "TEXT")
    private String filterJson;

    @Builder.Default
    @Column(name = "is_active", nullable = false)
    private boolean isActive = true;
}
