package com.example.timtro.entity;

import jakarta.persistence.*;
import lombok.*;

import java.util.UUID;

@Entity
@Table(name = "listing_costs")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ListingCost {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "listing_id", nullable = false)
    private Listing listing;

    @Column(name = "electricity_price")
    private Double electricityPrice;

    @Column(name = "water_price")
    private Double waterPrice;

    @Column(name = "internet_price")
    private Double internetPrice;
}
