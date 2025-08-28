FROM node:20-alpine
WORKDIR /ui

# Copy package files first
COPY frontend/package.json /ui/

# Use install instead of ci (works even if lock file is missing)
RUN npm install

# Copy the rest of the frontend code
COPY frontend /ui

EXPOSE 5173
CMD ["npm","run","dev","--","--host","0.0.0.0","--port","5173"]
