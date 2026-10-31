FROM node:22-alpine AS build
WORKDIR /app
COPY web_client/package*.json ./web_client/
RUN cd web_client && npm ci
COPY web_admin/package*.json ./web_admin/
RUN cd web_admin && npm ci
COPY web_client/src ./web_client/src
COPY web_admin/src ./web_admin/src
COPY web_admin/index.html web_admin/vite.config.js ./web_admin/
WORKDIR /app/web_admin
RUN npm run build
FROM nginx:alpine
COPY web_admin/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/web_admin/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
