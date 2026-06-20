package com.example.timtro.exception;

public class PaymentRequiredException extends RuntimeException {
    public PaymentRequiredException(String message) {
        super(message);
    }
}
