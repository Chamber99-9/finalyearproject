# Sajilo Loan frontend (Next.js) — production container for local Docker runs.
FROM node:22-slim

WORKDIR /app

# Install dependencies first for layer caching.
COPY package*.json ./
RUN npm install

# Copy source and build the production bundle.
COPY . .
RUN npm run build

EXPOSE 3000

# next start binds 0.0.0.0:3000 so it's reachable from the host browser.
CMD ["npm", "run", "start"]
