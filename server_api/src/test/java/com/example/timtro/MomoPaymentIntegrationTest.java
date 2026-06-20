package com.example.timtro;

import com.example.timtro.config.MomoProperties;
import com.example.timtro.dto.response.PaymentInitResponse;
import com.example.timtro.entity.PaymentTransaction;
import com.example.timtro.entity.User;
import com.example.timtro.repository.PaymentTransactionRepository;
import com.example.timtro.service.MomoPaymentService;
import com.example.timtro.util.MomoSignatureUtil;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Proxy;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Kiểm thử luồng thanh toán MoMo:
 *  - signature() khớp known-answer (so với openssl).
 *  - createPremiumPayment() gọi sandbox thật và nhận về payUrl hợp lệ.
 *
 * Dùng dynamic Proxy cho repository để không cần DB / Spring context.
 * Test có gọi mạng tới sandbox MoMo.
 */
class MomoPaymentIntegrationTest {

    // Credential sandbox công khai của MoMo
    private static final String PARTNER = "MOMO";
    private static final String ACCESS = "F8BBA842ECF85";
    private static final String SECRET = "K951B6PE1waDMi640xX08PD3vg6EkVlz";
    private static final String ENDPOINT = "https://test-payment.momo.vn/v2/gateway/api/create";

    @Test
    void signature_matches_known_answer_vector() {
        String raw = "accessKey=F8BBA842ECF85&amount=10000&extraData=&ipnUrl=https://example.com/ipn"
                + "&orderId=ORDER123&orderInfo=test&partnerCode=MOMO"
                + "&redirectUrl=https://example.com/return&requestId=ORDER123&requestType=captureWallet";
        String expected = "64b9604d2faad6ec828e3267fd25549f6079629fff0a907684679be51703f60b";
        assertEquals(expected, MomoSignatureUtil.sign(raw, SECRET));
    }

    @Test
    void createPremiumPayment_returns_real_payUrl_from_sandbox() {
        MomoProperties props = new MomoProperties();
        props.setPartnerCode(PARTNER);
        props.setAccessKey(ACCESS);
        props.setSecretKey(SECRET);
        props.setEndpoint(ENDPOINT);
        props.setRedirectUrl("https://example.com/payment/result");
        props.setIpnUrl("https://example.com/api/public/webhook/momo");
        props.setPremiumAmount(10000L);

        MomoPaymentService service = new MomoPaymentService(props, fakeRepository());

        User user = User.builder().email("landlord-test@example.com").build();

        PaymentInitResponse response = service.createPremiumPayment(user);

        assertNotNull(response, "Phản hồi không được null");
        assertNotNull(response.getPayUrl(), "payUrl phải khác null");
        assertTrue(response.getPayUrl().startsWith("https://test-payment.momo.vn"),
                "payUrl phải trỏ tới cổng thanh toán MoMo, nhận được: " + response.getPayUrl());
        assertNotNull(response.getOrderId());
        System.out.println("[MoMo TEST] payUrl = " + response.getPayUrl());
        System.out.println("[MoMo TEST] qrCodeUrl = " + response.getQrCodeUrl());
    }

    /** Repository giả lập bằng dynamic Proxy: save() trả lại entity, các method khác trả null. */
    private PaymentTransactionRepository fakeRepository() {
        return (PaymentTransactionRepository) Proxy.newProxyInstance(
                getClass().getClassLoader(),
                new Class[]{PaymentTransactionRepository.class},
                (proxy, method, args) -> {
                    if ("save".equals(method.getName()) && args != null && args.length == 1) {
                        return args[0];
                    }
                    if (method.getReturnType().equals(boolean.class)) {
                        return false;
                    }
                    return null;
                });
    }
}
