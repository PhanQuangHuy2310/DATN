package com.example.timtro.service;

import com.example.timtro.dto.response.MessageResponse;
import com.example.timtro.entity.FavoriteListing;
import com.example.timtro.entity.Listing;
import com.example.timtro.entity.User;
import com.example.timtro.repository.FavoriteListingRepository;
import com.example.timtro.repository.ListingRepository;
import com.example.timtro.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class FavoriteService {

    private final FavoriteListingRepository favoriteListingRepository;
    private final UserRepository userRepository;
    private final ListingRepository listingRepository;

    @Transactional
    public MessageResponse toggleFavorite(String email, UUID listingId) {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new IllegalArgumentException("Người dùng không tồn tại"));

        Listing listing = listingRepository.findById(listingId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy tin đăng"));

        return favoriteListingRepository.findByUserAndListing(user, listing)
                .map(favorite -> {
                    favoriteListingRepository.delete(favorite);
                    return new MessageResponse("Đã bỏ lưu tin đăng khỏi danh sách yêu thích");
                })
                .orElseGet(() -> {
                    FavoriteListing newFavorite = FavoriteListing.builder()
                            .user(user)
                            .listing(listing)
                            .build();
                    favoriteListingRepository.save(newFavorite);
                    return new MessageResponse("Đã lưu tin đăng vào danh sách yêu thích");
                });
    }

    @Transactional(readOnly = true)
    public Page<Listing> getMyFavoriteListings(String email, Pageable pageable) {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new IllegalArgumentException("Người dùng không tồn tại"));

        Page<FavoriteListing> favorites = favoriteListingRepository.findByUserOrderByCreatedAtDesc(user, pageable);
        return favorites.map(FavoriteListing::getListing);
    }
}
