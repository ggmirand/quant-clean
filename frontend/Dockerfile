FROM node:20-alpine
WORKDIR /ui

# Install dependencies
COPY frontend/package.json /ui/
RUN npm install

# Copy app source
COPY frontend /ui

EXPOSE 5173

# ✅ Correct CMD — Vite needs args after `--`
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

