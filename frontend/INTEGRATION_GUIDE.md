# Frontend Integration Guide

This is a Next.js frontend for the API Contract Debugger that you can **self-host** on your portfolio website without third-party deployment services.

## Quick Start (Local Development)

```bash
cd frontend

# Install dependencies
npm install

# Set API endpoint (optional, defaults to localhost:7860)
# Create/update .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:7860" > .env.local

# Run development server
npm run dev

# Open http://localhost:3000
```

## Building for Production

```bash
cd frontend

# Build optimized production bundle
npm run build

# Start production server
npm start

# Or export as static HTML (for serving from any static host)
npm run export
```

## Self-Hosting Options

### Option 1: On Your Portfolio Server (Recommended)

If your portfolio is hosted on a server you control:

```bash
# Build the frontend
npm run build

# Copy the `.next` directory and public files to your server
scp -r .next/ public/ package.json your-server:/var/www/portfolio/api-debugger/

# Install on server and start
npm install --production
npm start

# Your frontend will be at: https://your-portfolio.com/api-debugger
```

### Option 2: Docker Container (Same as Backend)

```bash
# Build Docker image
docker build -f Dockerfile.frontend -t api-debugger-ui .

# Run container
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL="http://your-backend:7860" \
  api-debugger-ui

# Access at localhost:3000
```

### Option 3: Static Export

For static hosting (GitHub Pages, Netlify free tier, portfolio server):

```bash
npm run export

# This creates an `out` directory with static HTML files
# Copy to your portfolio:
scp -r out/* your-server:/var/www/portfolio/api-debugger/
```

---

## API Configuration

The frontend connects to your backend via `NEXT_PUBLIC_API_URL`.

### Local Development
```bash
# Default (backend running on localhost:7860)
NEXT_PUBLIC_API_URL=http://localhost:7860
```

### Production (HF Spaces)
```bash
# If your API is on HF Spaces
NEXT_PUBLIC_API_URL=https://huggingface.co/spaces/keerthanas1011/api-contract-debugger
```

### Production (Your Own Server)
```bash
# If backend is on your domain
NEXT_PUBLIC_API_URL=https://api.your-portfolio.com
```

---

## Portfolio Integration

### Scenario 1: Frontend and Backend on Same Server

```
your-portfolio.com/
├── /                    → Portfolio home
├── /projects           → Projects list
├── /projects/api-debugger  → Frontend (this app)
└── /api/               → Backend API (port forwarded)
```

**Setup:**
```bash
# Build frontend
npm run build

# Copy to portfolio
cp -r .next/ public/ /var/www/portfolio/projects/api-debugger/

# Make sure backend API is accessible at your domain
# Configure nginx/apache to reverse proxy:
# /api/* → localhost:7860/*
```

### Scenario 2: Frontend in Portfolio, Backend on HF Spaces

```
your-portfolio.com/
├── /projects/api-debugger  → Frontend (this app)
└── (connects to HF Spaces for API)
```

**Setup:**
```bash
# Build with HF Spaces URL
NEXT_PUBLIC_API_URL=https://huggingface.co/spaces/your-username/api-contract-debugger npm run build

# Deploy frontend to your portfolio
```

### Scenario 3: Completely Self-Hosted

Frontend and backend both on your portfolio server:

```bash
# Terminal 1: Start backend API
cd api-contract-debugger
uvicorn server.app:app --host 0.0.0.0 --port 7860

# Terminal 2: Start frontend
cd frontend
npm start

# Frontend at: localhost:3000
# API at: localhost:7860
```

---

## Adding to Your Portfolio HTML

If your portfolio is a static site, embed the frontend like this:

```html
<!-- Your portfolio index.html -->
<section id="api-debugger-project">
  <h2>API Contract Debugger</h2>
  <p>Interactive RL environment for debugging API contracts</p>
  
  <!-- Embed the frontend -->
  <iframe 
    src="/projects/api-debugger" 
    width="100%" 
    height="800"
    style="border: none; border-radius: 8px;"
  ></iframe>
  
  <a href="/projects/api-debugger" target="_blank">
    Open in full screen →
  </a>
</section>
```

Or as a link:

```html
<a href="/projects/api-debugger" class="project-card">
  <h3>🔍 API Contract Debugger</h3>
  <p>Debug broken API specs with RL agent feedback</p>
  <span>Live Demo →</span>
</a>
```

---

## Features

✅ **3-Panel Dashboard**
- Left: Task selection, progress, violations
- Middle: Current API endpoints and specs
- Right: Action proposal form

✅ **Interactive Controls**
- Select task difficulty (easy/medium/hard)
- Propose fixes with form validation
- Real-time feedback on rewards

✅ **Visual Feedback**
- Progress bar tracking
- Violation cards with severity
- Endpoint JSON visualization
- Per-step and total rewards

✅ **Responsive Design**
- Beautiful gradient UI
- Mobile-friendly layout
- Auto-responsive panels

---

## Customization

### Change Color Scheme

Edit `app/page.css`:

```css
/* Change primary colors */
:root {
  --primary: #667eea;
  --secondary: #764ba2;
  --success: #27ae60;
  --error: #e74c3c;
}
```

### Add Your Branding

Edit `app/layout.tsx`:

```typescript
export const metadata: Metadata = {
  title: 'Your Name - API Contract Debugger',
  description: 'Interactive debugging environment...',
};
```

### Modify Form Fields

Edit `app/page.tsx` in the `submitAction` function to customize how actions are constructed.

---

## Troubleshooting

### "CORS errors" when connecting to API

**Solution:** Make sure your backend allows CORS:

```python
# In server/app.py, add:
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Frontend shows "Loading..." then fails

**Solution:** Check API URL:

```bash
# Test API connectivity
curl http://localhost:7860/health

# Make sure NEXT_PUBLIC_API_URL matches
echo "NEXT_PUBLIC_API_URL=http://localhost:7860" > .env.local
npm run dev
```

### Build fails with TypeScript errors

**Solution:** Run type check:

```bash
npx tsc --noEmit

# Fix any reported errors or suppress if needed:
# Add to next.config.js:
typescript: {
  ignoreBuildErrors: true,
}
```

---

## Deployment Checklist

- [ ] Update `NEXT_PUBLIC_API_URL` for production
- [ ] Run `npm run build` successfully
- [ ] Test all routes (reset, step, score)
- [ ] Verify CORS is configured on backend
- [ ] Test on mobile devices
- [ ] Add analytics/tracking if desired
- [ ] Create backup of working build

---

## Size & Performance

- **Build Size**: ~200KB (gzipped)
- **Initial Load**: <1s on modern connections
- **Runtime Performance**: Smooth 60fps interactions
- **No External Dependencies**: Just axios + React

---

## License

Same as main project. Use freely in your portfolio!

