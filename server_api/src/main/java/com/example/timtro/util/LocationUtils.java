package com.example.timtro.util;

import java.util.List;

public class LocationUtils {

    // Bán kính trái đất tính bằng Kilometers
    private static final double EARTH_RADIUS_KM = 6371.0;

    /**
     * DTO nội bộ đại diện cho toạ độ Kinh độ / Vĩ độ
     */
    public static class Coordinate {
        public double lat;
        public double lng;

        public Coordinate(double lat, double lng) {
            this.lat = lat;
            this.lng = lng;
        }
    }

    /**
     * Tính toạ độ Điểm Trung Vị (Midpoint / Centroid) của N toạ độ trên bề mặt cầu.
     * Sử dụng chuyển đổi sang hệ toạ độ Descartes 3D để đảm bảo độ chính xác trên bề mặt Trái Đất.
     *
     * @param coordinates Danh sách các toạ độ (Kinh độ, Vĩ độ)
     * @return Toạ độ điểm trung vị
     */
    public static Coordinate calculateGeographicMidpoint(List<Coordinate> coordinates) {
        if (coordinates == null || coordinates.isEmpty()) {
            throw new IllegalArgumentException("Danh sách toạ độ không được trống");
        }

        if (coordinates.size() == 1) {
            return coordinates.get(0);
        }

        double sumX = 0;
        double sumY = 0;
        double sumZ = 0;

        // 1. Chuyển đổi từng toạ độ sang hệ Descartes 3D và cộng dồn
        for (Coordinate coord : coordinates) {
            double latRad = Math.toRadians(coord.lat);
            double lngRad = Math.toRadians(coord.lng);

            sumX += Math.cos(latRad) * Math.cos(lngRad);
            sumY += Math.cos(latRad) * Math.sin(lngRad);
            sumZ += Math.sin(latRad);
        }

        // 2. Lấy trung bình cộng của X, Y, Z
        int totalPoints = coordinates.size();
        double avgX = sumX / totalPoints;
        double avgY = sumY / totalPoints;
        double avgZ = sumZ / totalPoints;

        // 3. Chuyển ngược lại từ X, Y, Z sang Vĩ độ (Lat) và Kinh độ (Lng)
        double hyp = Math.sqrt(avgX * avgX + avgY * avgY);
        double midLatRad = Math.atan2(avgZ, hyp);
        double midLngRad = Math.atan2(avgY, avgX);

        // 4. Chuyển từ radians sang degrees
        double midLat = Math.toDegrees(midLatRad);
        double midLng = Math.toDegrees(midLngRad);

        return new Coordinate(midLat, midLng);
    }

    /**
     * Áp dụng công thức Haversine để tính khoảng cách đường chim bay giữa 2 toạ độ.
     *
     * @param lat1 Vĩ độ điểm 1
     * @param lng1 Kinh độ điểm 1
     * @param lat2 Vĩ độ điểm 2
     * @param lng2 Kinh độ điểm 2
     * @return Khoảng cách tính bằng Kilometers
     */
    public static double calculateHaversineDistance(double lat1, double lng1, double lat2, double lng2) {
        double latDistance = Math.toRadians(lat2 - lat1);
        double lngDistance = Math.toRadians(lng2 - lng1);

        double a = Math.sin(latDistance / 2) * Math.sin(latDistance / 2)
                + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2))
                * Math.sin(lngDistance / 2) * Math.sin(lngDistance / 2);

        double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

        return EARTH_RADIUS_KM * c;
    }
}
