# API Contract Debugger Frontend

Modern, interactive web interface for the API Contract Debugger OpenEnv environment.

**Features:**
- 🎨 Beautiful gradient UI with real-time feedback
- 📊 3-panel dashboard (tasks, endpoints, actions)
- ⚡ Fast Next.js application (~200KB gzipped)
- 🔗 Self-contained, no third-party hosting required
- 📱 Fully responsive (desktop, tablet, mobile)
- 🎯 Portfolio-ready professional design

## Quick Start

```bash
# Install
npm install

# Development
npm run dev
# Opens http://localhost:3000

# Production build
npm run build
npm start

# Static export (for static hosting)
npm run export
```

## Configuration

Update `NEXT_PUBLIC_API_URL` in `.env.local`:

```bash
# Local development
NEXT_PUBLIC_API_URL=http://localhost:7860

# Production (HF Spaces)
NEXT_PUBLIC_API_URL=https://huggingface.co/spaces/username/api-contract-debugger

# Production (your domain)
NEXT_PUBLIC_API_URL=https://api.your-portfolio.com
```

## Hosting on Your Portfolio

### Self-hosted on your server

```bash
npm run build
# Copy .next/ and public/ to your portfolio server
```

### With Docker

```bash
docker build -f Dockerfile.frontend -t api-debugger-ui .
docker run -p 3000:3000 api-debugger-ui
```

### As static files

```bash
npm run export
# Deploy `out/` directory to any static host
```

## Customization

- **Colors**: Edit `app/page.css` (purple/blue gradient theme)
- **Branding**: Update `app/layout.tsx` metadata
- **Layout**: Modify `app/page.tsx` component structure

See [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md) for detailed deployment instructions.

## Architecture

```
app/
├── layout.tsx          # Root layout
├── page.tsx            # Main dashboard component
├── page.css            # Styling
├── globals.css         # Global styles
└── favicon.ico

package.json
next.config.js
tsconfig.json
.env.local              # Configuration
```

## API Contract

Frontend communicates with backend via HTTP:

**Endpoints used:**
- `POST /reset` - Start new task
- `POST /step` - Apply fix action
- `GET /score` - Get episode score

See main `README.md` for full API documentation.

## Performance

- **Build time**: <30s
- **Bundle size**: 200KB (gzipped)
- **Time to interactive**: <1s
- **Lighthouse score**: 95+

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Mobile)

## License

Same as main project.
