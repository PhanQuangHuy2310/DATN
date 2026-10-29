FROM node:22-alpine AS build
WORKDIR /app
COPY web_client/package*.json ./
RUN npm ci
COPY web_client/ ./
RUN npm run build

FROM nginx:alpine
RUN apk upgrade --no-cache \
    && apk del --no-network nginx-module-image-filter libgd fontconfig libexpat
COPY web_client/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
