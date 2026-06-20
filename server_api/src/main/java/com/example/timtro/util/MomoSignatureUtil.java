package com.example.timtro.util;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;

/**
 * Tiện ích ký chữ ký HMAC-SHA256 theo chuẩn MoMo.
 * Chuỗi raw được sắp xếp khóa theo a-z trước khi ký.
 */
public final class MomoSignatureUtil {

    private MomoSignatureUtil() {
    }

    /** Ký chuỗi {@code data} bằng {@code secretKey}, trả về hex thường (lowercase). */
    public static String sign(String data, String secretKey) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secretKey.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] hash = mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                sb.append(Character.forDigit((b >> 4) & 0xF, 16));
                sb.append(Character.forDigit(b & 0xF, 16));
            }
            return sb.toString();
        } catch (Exception e) {
            throw new IllegalStateException("Không thể tạo chữ ký HMAC-SHA256 cho MoMo", e);
        }
    }
}
