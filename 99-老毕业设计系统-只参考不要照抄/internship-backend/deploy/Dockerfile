FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production TZ=Asia/Shanghai
COPY package*.json ./
RUN npm ci --omit=dev || npm install --omit=dev
COPY . .
RUN mkdir -p uploads && addgroup -S app && adduser -S app -G app && chown -R app:app /app
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://localhost:3000/api/health || exit 1
CMD ["node","app.js"]
