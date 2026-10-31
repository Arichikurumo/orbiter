FROM node:24-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY server.js fetch-images.js prices.js syndprices.js ./
COPY site site
RUN mkdir /data && chown node:node /data
USER node
# The database and the downloaded pictures live in /data, so mount a volume there.
ENV DB=/data/state.db IMG_DIR=/data/img PORT=8080
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD node -e "fetch('http://127.0.0.1:8080/healthz').then(r=>process.exit(r.ok?0:1),()=>process.exit(1))"
CMD ["node", "server.js"]
