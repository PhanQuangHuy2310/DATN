package com.example.timtro.controller;

import com.example.timtro.dto.request.MomoCallbackDTO;
import com.example.timtro.service.MomoWebhookService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/public/webhook")
@RequiredArgsConstructor
@Slf4j
public class WebhookController {

    private final MomoWebhookService momoWebhookService;

    @PostMapping("/momo")
    public ResponseEntity<Void> handleMomoCallback(@RequestBody MomoCallbackDTO callbackDTO) {
        try {
            momoWebhookService.processMomoCallback(callbackDTO);
            // MoMo requires HTTP 204 No Content for successful callback acknowledgement
            return ResponseEntity.noContent().build();
        } catch (Exception e) {
            log.error("Error processing MoMo callback", e);
            // Return 204 anyway so MoMo won't retry excessively if it's our internal error (e.g. order not found)
            return ResponseEntity.noContent().build(); 
        }
    }
}
