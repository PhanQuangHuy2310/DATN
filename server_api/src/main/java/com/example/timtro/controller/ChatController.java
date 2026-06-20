package com.example.timtro.controller;

import com.example.timtro.dto.request.ChatMessageRequest;
import com.example.timtro.entity.ChatMessage;
import com.example.timtro.entity.User;
import com.example.timtro.repository.ChatMessageRepository;
import com.example.timtro.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Controller;

import java.security.Principal;
import java.util.UUID;

@Controller
@RequiredArgsConstructor
public class ChatController {

    private final SimpMessagingTemplate messagingTemplate;
    private final ChatMessageRepository chatMessageRepository;
    private final UserRepository userRepository;

    @MessageMapping("/chat.send")
    public void sendMessage(@Payload ChatMessageRequest request, Principal principal) {
        if (principal == null) {
            throw new IllegalArgumentException("User chưa xác thực");
        }

        String senderEmail = principal.getName();
        User sender = userRepository.findByEmail(senderEmail)
                .orElseThrow(() -> new IllegalArgumentException("Sender không tồn tại"));

        User receiver = userRepository.findById(request.getReceiverId())
                .orElseThrow(() -> new IllegalArgumentException("Receiver không tồn tại"));

        ChatMessage message = ChatMessage.builder()
                .sender(sender)
                .receiver(receiver)
                .content(request.getContent())
                .build();

        // Lưu vào DB
        message = chatMessageRepository.save(message);

        // Đẩy tin nhắn qua STOMP /user/{receiverId}/queue/messages
        messagingTemplate.convertAndSendToUser(
                receiver.getId().toString(),
                "/queue/messages",
                message
        );
    }
}
