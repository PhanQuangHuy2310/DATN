package com.example.timtro.dto.request;

import lombok.Data;

import java.util.UUID;

@Data
public class ChatMessageRequest {
    private UUID receiverId;
    private String content;
}
