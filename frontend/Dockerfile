FROM node:18-slim
WORKDIR /app
COPY . .
RUN npm install          # Fix #18: was missing entirely
RUN npm run build
CMD ["npx", "serve", "-s", "build", "-l", "3000"]
