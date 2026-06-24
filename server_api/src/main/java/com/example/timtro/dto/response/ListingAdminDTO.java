package com.example.timtro.dto.response;

import com.example.timtro.entity.ListingStatus;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ListingAdminDTO {
    private UUID id;
    private String title;
    private Double price;
    private Double area;
    private String address; // Will map to a substring of description or we'll fake it from geom/description if no address field
    private String ownerName;
    private ListingStatus status;
    private LocalDateTime createdAt;
    private String imageUrl; // First image from attachments
}
