package com.example.timtro;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class ServerApiApplication {

	public static void main(String[] args) {
		SpringApplication.run(ServerApiApplication.class, args);
	}

}
