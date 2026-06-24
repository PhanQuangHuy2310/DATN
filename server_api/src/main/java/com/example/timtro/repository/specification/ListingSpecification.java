package com.example.timtro.repository.specification;

import com.example.timtro.entity.Listing;
import com.example.timtro.entity.ListingStatus;
import org.springframework.data.jpa.domain.Specification;

import java.math.BigDecimal;

public class ListingSpecification {

    public static Specification<Listing> hasStatus(ListingStatus status) {
        return (root, query, cb) -> cb.equal(root.get("status"), status);
    }

    public static Specification<Listing> hasTitleContaining(String keyword) {
        return (root, query, cb) -> cb.like(cb.lower(root.get("title")), "%" + keyword.toLowerCase() + "%");
    }

    public static Specification<Listing> priceGreaterThanOrEqualTo(BigDecimal minPrice) {
        return (root, query, cb) -> cb.greaterThanOrEqualTo(root.get("price"), minPrice);
    }

    public static Specification<Listing> priceLessThanOrEqualTo(BigDecimal maxPrice) {
        return (root, query, cb) -> cb.lessThanOrEqualTo(root.get("price"), maxPrice);
    }

    public static Specification<Listing> areaGreaterThanOrEqualTo(Double minArea) {
        return (root, query, cb) -> cb.greaterThanOrEqualTo(root.get("area"), minArea);
    }

    public static Specification<Listing> areaLessThanOrEqualTo(Double maxArea) {
        return (root, query, cb) -> cb.lessThanOrEqualTo(root.get("area"), maxArea);
    }

}

