# Multi-stage: build the Vite app with Node, then serve the static dist/ with nginx.
# Pass the backend URL at build time:
#   docker build --build-arg VITE_API_BASE=http://api.example:8000 -t carecompass-web .

# ---- build ----
FROM node:22-alpine AS build
WORKDIR /app

# Install deps first for better layer caching.
COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY . .

# Env baked into the static build. Default to the live backend (no mocks).
ARG VITE_API_BASE=http://localhost:8000
ARG VITE_USE_MOCKS=0
ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_USE_MOCKS=$VITE_USE_MOCKS

RUN npm run build

# ---- serve ----
FROM nginx:1.27-alpine AS serve
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
# a checkout made with a strict umask (e.g. 0007) would leave the icons unreadable to nginx (403)
RUN chmod -R a+rX /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
