# syntax=docker/dockerfile:1
# ----------------------------------------------------------------------------
# AI DB Advisor — web UI (the React/Vite SPA that the Tauri app wraps), served
# by nginx. Build context is tauri-app/.
# ----------------------------------------------------------------------------

# ---- Build the SPA ----------------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Same-origin: the app calls /api/* and nginx proxies that to the backend.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build   # tsc && vite build -> /app/dist

# ---- Serve with nginx -------------------------------------------------------
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
