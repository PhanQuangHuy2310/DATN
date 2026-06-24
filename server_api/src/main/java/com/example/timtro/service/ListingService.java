package com.example.timtro.service;

import com.example.timtro.dto.request.ListingCreateRequest;
import com.example.timtro.dto.response.ListingDistanceProjection;
import com.example.timtro.entity.Listing;
import com.example.timtro.entity.ListingCost;
import com.example.timtro.entity.ListingStatus;
import com.example.timtro.entity.User;
import com.example.timtro.exception.PaymentRequiredException;
import com.example.timtro.repository.ListingRepository;
import com.example.timtro.util.GeometryUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class ListingService {

    private final ListingRepository listingRepository;

    @Transactional
    public UUID createListing(ListingCreateRequest request, User landlord) {
        int activeListingCount = listingRepository.countByUserAndStatusNot(landlord, ListingStatus.HIDDEN);
        
        if (activeListingCount >= 5) {
            LocalDateTime premiumExpiry = landlord.getPremiumExpiryDate();
            if (premiumExpiry == null || premiumExpiry.isBefore(LocalDateTime.now())) {
                throw new PaymentRequiredException("Bạn đã hết 5 tin đăng miễn phí. Vui lòng thanh toán 10.000VND để đăng tin tiếp theo.");
            }
        }

        Listing listing = Listing.builder()
                .title(request.getTitle())
                .description(request.getDescription())
                .price(request.getPrice())
                .area(request.getArea())
                .maxMotorbikes(request.getMaxMotorbikes())
                .geom(GeometryUtil.createPoint(request.getLat(), request.getLng()))
                .status(ListingStatus.PENDING)
                .user(landlord)
                .build();

        if (request.getListingCosts() != null) {
            ListingCost listingCost = ListingCost.builder()
                    .listing(listing)
                    .electricityPrice(request.getListingCosts().getElectricityPrice())
                    .waterPrice(request.getListingCosts().getWaterPrice())
                    .internetPrice(request.getListingCosts().getInternetPrice())
                    .build();
            listing.setListingCost(listingCost);
        }

        listing = listingRepository.save(listing);
        return listing.getId();
    }

    public List<ListingDistanceProjection> searchListingsByRadius(double lat, double lng, double radiusInMeters) {
        return listingRepository.findListingsWithinRadius(lat, lng, radiusInMeters);
    }

    @Transactional(readOnly = true)
    public org.springframework.data.domain.Page<Listing> searchListings(
            String keyword, java.math.BigDecimal minPrice, java.math.BigDecimal maxPrice,
            Double minArea, Double maxArea, org.springframework.data.domain.Pageable pageable) {

        org.springframework.data.jpa.domain.Specification<Listing> spec = org.springframework.data.jpa.domain.Specification.where(
                com.example.timtro.repository.specification.ListingSpecification.hasStatus(ListingStatus.APPROVED));

        if (keyword != null && !keyword.trim().isEmpty()) {
            spec = spec.and(com.example.timtro.repository.specification.ListingSpecification.hasTitleContaining(keyword));
        }
        if (minPrice != null) {
            spec = spec.and(com.example.timtro.repository.specification.ListingSpecification.priceGreaterThanOrEqualTo(minPrice));
        }
        if (maxPrice != null) {
            spec = spec.and(com.example.timtro.repository.specification.ListingSpecification.priceLessThanOrEqualTo(maxPrice));
        }
        if (minArea != null) {
            spec = spec.and(com.example.timtro.repository.specification.ListingSpecification.areaGreaterThanOrEqualTo(minArea));
        }
        if (maxArea != null) {
            spec = spec.and(com.example.timtro.repository.specification.ListingSpecification.areaLessThanOrEqualTo(maxArea));
        }

        return listingRepository.findAll(spec, pageable);
    }

    @Transactional
    public void changeListingStatus(UUID listingId, ListingStatus newStatus, String userEmail) {
        Listing listing = listingRepository.findById(listingId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy tin đăng"));

        if (!listing.getUser().getEmail().equals(userEmail)) {
            throw new IllegalArgumentException("Bạn không có quyền cập nhật tin đăng này");
        }

        listing.setStatus(newStatus);
        listingRepository.save(listing);
    }

    public com.example.timtro.dto.response.MidpointSearchResponseDTO searchByMidpoint(com.example.timtro.dto.request.MidpointSearchRequestDTO request) {
        org.locationtech.jts.geom.Point midpoint = GeometryUtil.calculateMidpoint(request.getCoordinates());
        if (midpoint == null) {
            throw new IllegalArgumentException("Không thể tính toán điểm trung vị từ danh sách tọa độ");
        }

        List<ListingDistanceProjection> listings = searchListingsByRadius(midpoint.getY(), midpoint.getX(), request.getRadius());

        com.example.timtro.dto.request.CoordinateDTO midpointDto = new com.example.timtro.dto.request.CoordinateDTO();
        midpointDto.setLat(midpoint.getY());
        midpointDto.setLng(midpoint.getX());

        return com.example.timtro.dto.response.MidpointSearchResponseDTO.builder()
                .midpoint(midpointDto)
                .listings(listings)
                .build();
    }
    public List<com.example.timtro.dto.response.PoiDTO> getNearbyPois(UUID listingId) {
        Listing listing = listingRepository.findById(listingId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy tin đăng"));

        // Mock POI Data (Trong thực tế sẽ gọi Google Places API hoặc Overpass API dựa trên listing.getGeom())
        return List.of(
                com.example.timtro.dto.response.PoiDTO.builder().name("Siêu thị Vinmart").type("supermarket").distanceInMeters(150.5).build(),
                com.example.timtro.dto.response.PoiDTO.builder().name("Trạm xe buýt ngã tư").type("bus_station").distanceInMeters(300.0).build(),
                com.example.timtro.dto.response.PoiDTO.builder().name("Chợ dân sinh").type("market").distanceInMeters(450.2).build()
        );
    }

    @Transactional(readOnly = true)
    public Listing getListingById(UUID id) {
        return listingRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy tin đăng"));
    }

    @Transactional(readOnly = true)
    public List<Listing> getSimilarListings(UUID listingId) {
        Listing listing = getListingById(listingId);
        double minPrice = listing.getPrice() * 0.9;
        double maxPrice = listing.getPrice() * 1.1;
        
        return listingRepository.findSimilarListingsNative(
                listing.getId(), 
                minPrice, 
                maxPrice, 
                listing.getGeom().getY(), 
                listing.getGeom().getX(), 
                5000.0, // 5km bán kính
                5 // limit 5
        );
    }

    @Transactional(readOnly = true)
    public List<Listing> getListingsByIds(List<UUID> ids) {
        return listingRepository.findAllById(ids);
    }
}
