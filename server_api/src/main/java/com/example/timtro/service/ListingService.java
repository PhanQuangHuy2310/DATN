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
        // 1. Kiểm tra số lượng tin đăng hiện tại (không bị xóa/hủy/ẩn)
        // Coi như các tin PENDING, APPROVED, RENTED là tin đang sử dụng hạn mức
        // (Hoặc tuỳ logic thực tế, tạm đếm các tin khác REJECTED và HIDDEN)
        int activeListingCount = listingRepository.countByUserAndStatusNot(landlord, ListingStatus.HIDDEN);
        
        // Nếu user có tin thứ 5 trở lên đã bị REJECTED thì vẫn tính là hạn ngạch? Tạm đếm khác HIDDEN.
        
        // Theo yêu cầu: nếu có từ 6 bài đăng trở lên (tức là active >= 5) thì phải check premium
        if (activeListingCount >= 5) {
            LocalDateTime premiumExpiry = landlord.getPremiumExpiryDate();
            if (premiumExpiry == null || premiumExpiry.isBefore(LocalDateTime.now())) {
                throw new PaymentRequiredException("Bạn đã hết 5 tin đăng miễn phí. Vui lòng thanh toán 10.000VND để đăng tin tiếp theo.");
            }
        }

        // 2. Map DTO -> Entity
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

        // Map Costs
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
}
