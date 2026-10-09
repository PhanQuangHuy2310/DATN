FROM node:22.23.3-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS build
WORKDIR /app
COPY web_client/package*.json ./
RUN npm ci
COPY web_client/ ./
RUN npm run build

FROM nginx:1.31.6-alpine@sha256:df221db836e1754089190208cee7eeda94f233197056426eda74a43ab1abeac2
RUN apk upgrade --no-cache \
    && apk del --no-network nginx-module-image-filter libgd fontconfig libexpat
COPY web_client/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
