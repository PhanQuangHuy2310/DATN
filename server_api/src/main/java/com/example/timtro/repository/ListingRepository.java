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

import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

@Repository
public interface ListingRepository extends JpaRepository<Listing, UUID>, JpaSpecificationExecutor<Listing> {

    int countByUserAndStatusNot(User user, ListingStatus status);

    int countByUser(User user);

    long countByStatus(ListingStatus status);

    List<Listing> findByUserOrderByCreatedAtAsc(User user);

    @Query(value = """
        SELECT id, title, price, area, 
               ST_Y(geom) as lat, ST_X(geom) as lng,
               ST_Distance(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), false) AS distance
        FROM listings
        WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), :radius)
          AND status = 'AVAILABLE'
        ORDER BY distance ASC
    """, nativeQuery = true)
    List<ListingDistanceProjection> findListingsWithinRadius(
            @Param("lat") double lat, 
            @Param("lng") double lng, 
            @Param("radius") double radius);

    @Query(value = """
        SELECT *
        FROM listings
        WHERE status = 'AVAILABLE'
          AND id != :excludeId
          AND price >= :minPrice AND price <= :maxPrice
          AND ST_DWithin(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), :radius)
        ORDER BY ST_Distance(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), false) ASC, created_at DESC
        LIMIT :limit
    """, nativeQuery = true)
    List<Listing> findSimilarListingsNative(
            @Param("excludeId") UUID excludeId,
            @Param("minPrice") double minPrice,
            @Param("maxPrice") double maxPrice,
            @Param("lat") double lat, 
            @Param("lng") double lng, 
            @Param("radius") double radius,
            @Param("limit") int limit);
}
