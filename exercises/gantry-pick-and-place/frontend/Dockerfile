# Frontend: build the dashboard with Node, serve it with nginx.
# Build context is the exercise root (see docker-compose.yml), because the
# typed API client is generated from ../backend/proto/app.proto.

FROM node:22-slim AS build
WORKDIR /src/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY backend/proto /src/backend/proto
COPY frontend/ ./

# Call the API on the same origin; nginx forwards /rpc to the backend.
ENV VITE_API_URL=/rpc
RUN npm run build


FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/frontend/dist /usr/share/nginx/html
EXPOSE 80
