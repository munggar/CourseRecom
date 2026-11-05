FROM node:20-alpine
WORKDIR /app
ARG VITE_API_BASE_URL=/api
ARG VITE_ENVIRONMENT=development
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_ENVIRONMENT=$VITE_ENVIRONMENT
ENV API_PROXY_TARGET=http://backend:8000
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 5173
CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "5173"]
