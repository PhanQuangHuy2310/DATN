package com.example.timtro.repository;

import com.example.timtro.dto.response.ListingDistanceProjection;
import com.example.timtro.entity.Listing;
import com.example.timtro.entity.ListingStatus;
import com.example.timtro.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

import java.util.UUID;

@Repository
public interface ListingRepository extends JpaRepository<Listing, UUID> {

    int countByUserAndStatusNot(User user, ListingStatus status);

    List<Listing> findByUserOrderByCreatedAtAsc(User user);

    @Query(value = """
        SELECT id, title, price, area, 
               ST_Distance(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), false) AS distance
        FROM listings
        WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), :radius)
          AND status = 'APPROVED'
        ORDER BY distance ASC
    """, nativeQuery = true)
    List<ListingDistanceProjection> findListingsWithinRadius(
            @Param("lat") double lat, 
            @Param("lng") double lng, 
            @Param("radius") double radius);
}
