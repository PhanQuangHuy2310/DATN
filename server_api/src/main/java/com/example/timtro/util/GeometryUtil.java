package com.example.timtro.util;

import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.GeometryFactory;
import org.locationtech.jts.geom.Point;
import org.locationtech.jts.geom.PrecisionModel;

public class GeometryUtil {

    /**
     * Tạo một GeometryFactory với SRID = 4326.
     * SRID 4326 là hệ tọa độ mà Google Maps và các hệ thống GPS hay dùng.
     */
    private static final GeometryFactory geometryFactory = new GeometryFactory(new PrecisionModel(), 4326);

    /**
     * Chuyển đổi cặp Vĩ độ (Lat) và Kinh độ (Lng) sang đối tượng Point (JTS).
     *
     * @param lat Vĩ độ (Latitude - Trục Y)
     * @param lng Kinh độ (Longitude - Trục X)
     * @return Đối tượng Point hoặc null nếu đầu vào không hợp lệ
     */
    public static Point createPoint(Double lat, Double lng) {
        if (lat == null || lng == null) {
            return null;
        }
        
        // Cực kỳ chú ý: Tọa độ truyền vào Constructor của Coordinate phải là (X, Y) -> (Kinh độ, Vĩ độ)
        Coordinate coordinate = new Coordinate(lng, lat);
        return geometryFactory.createPoint(coordinate);
    }
}
