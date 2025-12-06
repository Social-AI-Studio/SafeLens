# SafeLens Repository Guide

**Last Updated**: 2025-11-20
**Purpose**: Comprehensive reference for AI agents and developers working with the SafeLens codebase

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Architecture](#architecture)
4. [Project Structure](#project-structure)
5. [Getting Started](#getting-started)
6. [Backend (FastAPI)](#backend-fastapi)
7. [Frontend (Next.js)](#frontend-nextjs)
8. [Authentication Service](#authentication-service)
9. [Database Architecture](#database-architecture)
10. [Configuration Management](#configuration-management)
11. [Video Processing Pipeline](#video-processing-pipeline)
12. [API Reference](#api-reference)
13. [Testing Strategy](#testing-strategy)
14. [Deployment](#deployment)
15. [Key File Locations](#key-file-locations)

---

## Project Overview

**SafeLens** is a comprehensive hateful video moderation system that combines vision, language, and audio processing to detect harmful content in videos. The system analyzes videos through frame classification, OCR text extraction, audio transcription, and LLM-powered content analysis.

**Demo Video**: https://youtu.be/B1dYceLSnXA

**Core Capabilities**:
- Multi-modal video analysis (vision + audio + text)
- Real-time harmful content detection with timestamps
- Interactive video player with harmful event markers
- User authentication via OIDC with Google OAuth
- Support for both file uploads and URL-based video downloads (YouTube, Vimeo, etc.)
- Word-level transcription with synchronized playback

---

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Server**: Uvicorn with uvloop optimization
- **Database**: PostgreSQL 17.5 with SQLAlchemy 2.0.41
- **Migrations**: Alembic 1.16.4
- **Package Manager**: UV (preferred) or pip
- **ML/AI**:
  - vLLM - High-performance inference (Llama-3-8B-Instruct + LoRA, Qwen2.5-VL-7B)
  - WhisperX - Audio transcription with word alignment
  - Transformers - Vision Transformer (ViT) for scene detection
  - PyTesseract + EasyOCR - Optical character recognition
  - OpenCV + Pillow - Video frame extraction and processing

### Frontend
- **Framework**: Next.js 15 (App Router)
- **Runtime**: React 19.1.1
- **Language**: TypeScript (strict mode)
- **UI**: Radix UI + Tailwind CSS v4
- **Authentication**: Auth.js (next-auth) 5.0.0-beta.29
- **Data Fetching**: TanStack React Query v5.89.0
- **Video Player**: Video.js 8.23.4
- **Forms**: React Hook Form + Zod validation
- **Package Manager**: pnpm 8+

### Authentication Service
- **Framework**: Next.js 15
- **Auth Library**: Better Auth 1.3.13 (OIDC provider)
- **Database ORM**: Drizzle ORM 0.44.5
- **OAuth Provider**: Google OAuth 2.0
- **JWT Signing**: EdDSA (Ed25519)
- **Package Manager**: pnpm 8+

---

## Architecture

### Service Architecture

```
┌─────────────────┐
│   Frontend      │  Port 3000 (Next.js)
│  (localhost)    │
└────────┬────────┘
         │
         ├──────────────────┐
         │                  │
         v                  v
┌─────────────────┐  ┌─────────────────┐
│  Auth Service   │  │  Backend API    │
│  Port 3001      │  │  Port 8000      │
│  (Next.js +     │  │  (FastAPI)      │
│   Better Auth)  │  │                 │
└────────┬────────┘  └────────┬────────┘
         │                    │
         v                    v
┌─────────────────┐  ┌─────────────────┐
│  Auth DB        │  │  Backend DB     │
│  Port 5433      │  │  Port 5432      │
│  (PostgreSQL)   │  │  (PostgreSQL)   │
└─────────────────┘  └────────┬────────┘
                              │
                              v
                     ┌─────────────────┐
                     │  vLLM Inference │
                     │  Ports 8192,    │
                     │  8193 (GPU)     │
                     └─────────────────┘
```

### Component Responsibilities

**Frontend** (`web/frontend/`):
- User interface for video upload and analysis
- Video playback with synchronized transcription
- Harmful content visualization with timeline markers
- Authentication UI and session management

**Auth Service** (`auth-service/`):
- OIDC-compliant authentication provider
- Google OAuth integration
- Dynamic client registration (RFC 7591)
- JWT token issuance and JWKS endpoint
- Admin panel for user and client management

**Backend API** (`web/`):
- Video upload and URL download handling
- Analysis pipeline orchestration
- Database persistence
- Video streaming and thumbnail serving
- User registration and video management

**Databases**:
- Auth DB: User accounts, sessions, OAuth tokens, OIDC clients
- Backend DB: Videos, analysis results, harmful events, transcriptions

---

## Project Structure

```
SafeLens/
├── README.md                   # High-level overview
├── AGENTS.md                   # Team collaboration guidelines
├── CHECKPOINT.md               # Development status snapshot
├── REFACTOR_SPEC.md           # Refactoring specification
│
├── auth-service/              # OIDC Authentication Provider
│   ├── src/
│   │   ├── app/               # Next.js routes (sign-in, admin)
│   │   │   ├── sign-in/
│   │   │   ├── admin/
│   │   │   │   ├── apps/      # OIDC client management
│   │   │   │   └── layout.tsx # Admin protection
│   │   │   └── api/auth/[...all]/route.ts
│   │   ├── components/        # UI components
│   │   ├── db/
│   │   │   ├── schema.ts      # Drizzle schema (8 tables)
│   │   │   └── migrations/
│   │   ├── lib/
│   │   │   ├── auth.ts        # Better Auth config
│   │   │   └── auth-client.ts
│   │   └── scripts/
│   │       └── register-client.ts  # CLI registration
│   ├── package.json
│   ├── drizzle.config.ts
│   ├── .env.example
│   └── README.md
│
├── web/                       # Backend & Frontend
│   ├── server.py              # Uvicorn entry point
│   ├── api.py                 # FastAPI app setup
│   ├── database.py            # SQLAlchemy models
│   ├── config.py
│   ├── logging_config.py
│   │
│   ├── routers/               # API endpoints
│   │   ├── videos.py          # Video management
│   │   └── health.py          # Health checks
│   │
│   ├── services/              # Business logic
│   │   ├── analysis_pipeline.py
│   │   ├── url_downloader.py
│   │   ├── transcript.py
│   │   ├── segmentation_service.py
│   │   ├── reporting.py
│   │   ├── persistence.py
│   │   └── failures.py
│   │
│   ├── tools/                 # ML/AI wrappers
│   │   ├── llm.py             # SafetyLLM
│   │   ├── image_classifier.py
│   │   ├── transcription.py
│   │   ├── ocr.py
│   │   └── frame_extraction.py
│   │
│   ├── app/                   # Application modules
│   │   ├── orchestration/     # Analysis orchestration
│   │   ├── planning/          # LLM planning
│   │   ├── runtime/           # GPU guard, metrics
│   │   └── health/            # Provider health
│   │
│   ├── schemas/
│   │   └── responses.py       # Pydantic models
│   │
│   ├── background/
│   │   └── enqueue.py         # Background tasks
│   │
│   ├── alembic/               # Database migrations
│   │   └── versions/          # 10 migration files
│   │
│   ├── lora_adapter/          # LoRA fine-tuned model
│   ├── pyproject.toml
│   ├── .env.example
│   ├── README.md
│   │
│   └── frontend/              # Next.js Frontend
│       ├── src/
│       │   ├── app/           # App Router
│       │   │   ├── page.tsx   # Home/upload
│       │   │   ├── [videoId]/page.tsx
│       │   │   └── api/       # Backend proxies
│       │   ├── components/
│       │   │   ├── VideoPlayer.tsx
│       │   │   ├── VideoUpload.tsx
│       │   │   ├── AnalysisResults.tsx
│       │   │   ├── ClusteredAnalysisData.tsx
│       │   │   ├── SyncedLyrics.tsx
│       │   │   └── ui/        # Shadcn components
│       │   ├── context/
│       │   │   └── PlayerContext.tsx
│       │   ├── lib/
│       │   │   ├── auth.ts    # NextAuth config
│       │   │   └── validation.ts
│       │   ├── hooks/
│       │   ├── types/
│       │   │   └── analysis.ts
│       │   └── utils/
│       │       ├── clustering.ts
│       │       └── transcription.ts
│       ├── package.json
│       ├── .env.example
│       └── README.md
```

---

## Getting Started

### Prerequisites

- **Node.js**: 20 LTS
- **Python**: 3.11+
- **PostgreSQL**: 17.5+ (via Docker)
- **GPU**: CUDA-compatible GPU with 16GB+ VRAM (for vLLM inference)
- **Package Managers**: pnpm (Node.js), uv (Python)
- **Docker**: For database containers

### Quick Start (Local Development)

#### 1. Database Setup

```bash
# Backend database
docker run --name safelens_web_db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=safelens_web_db \
  -p 5432:5432 \
  -v safelens_web_data:/var/lib/postgresql/data \
  -d postgres:17.5

# Auth service database
docker run --name safelens_auth_db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=safelens_auth_db \
  -p 5433:5432 \
  -v safelens_auth_data:/var/lib/postgresql/data \
  -d postgres:17.5
```

#### 2. Backend Setup

```bash
cd web

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Install dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Start server
uv run uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

#### 3. Auth Service Setup

```bash
cd auth-service

# Copy environment file
cp .env.example .env
# Edit .env (add GOOGLE_CLIENT_ID/SECRET, generate BETTER_AUTH_SECRET)

# Install dependencies
pnpm install

# Run migrations
pnpm run db:migrate

# Start service
PORT=3001 pnpm dev

# Register frontend client
pnpm run register-client -- \
  --name "SafeLens Frontend" \
  --redirect "http://localhost:3000/api/auth/callback/socialai-studio-auth" \
  --type web
# Save the client_id and client_secret
```

#### 4. Frontend Setup

```bash
cd web/frontend

# Copy environment file
cp .env.example .env
# Edit .env (add AUTH_CLIENT_ID/SECRET from previous step)

# Install dependencies
pnpm install

# Start development server
pnpm dev
```

#### 5. vLLM Inference Servers (Optional for Analysis)

```bash
# Terminal 1: Llama-3-8B + LoRA
CUDA_VISIBLE_DEVICES=0 uvx vllm serve meta-llama/Meta-Llama-3-8B-Instruct \
  --host 0.0.0.0 --port 8192 \
  --enable-lora \
  --lora-modules SafeLens/llama-3-8b=/path/to/lora_adapter

# Terminal 2: Qwen2.5-VL
CUDA_VISIBLE_DEVICES=1 uvx vllm serve Qwen/Qwen2.5-VL-7B-Instruct \
  --host 0.0.0.0 --port 8193
```

#### 6. Access the Application

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Auth Service: http://localhost:3001
- Backend Health: http://localhost:8000/health
- OIDC Discovery: http://localhost:3001/api/auth/.well-known/openid-configuration

---

## Backend (FastAPI)

**Location**: `/home/definevera/Documents/RA/SafeLens/web/`

### Core Components

**API Structure**:
- `api.py` - FastAPI app initialization, CORS middleware
- `server.py` - Uvicorn server entry point with CLI args
- `database.py` - SQLAlchemy models and session management

**Key Services**:
- `analysis_pipeline.py` - Main video analysis orchestration
- `url_downloader.py` - yt-dlp wrapper for video downloads
- `transcript.py` - WhisperX transcription integration
- `segmentation_service.py` - Video segmentation logic
- `reporting.py` - Safety report generation
- `persistence.py` - Database saving operations

**ML Tools**:
- `llm.py` - SafetyLLM with multi-backend routing (HTTP/OpenRouter)
- `image_classifier.py` - Vision model classification
- `transcription.py` - WhisperX wrapper
- `ocr.py` - PyTesseract + EasyOCR integration
- `frame_extraction.py` - OpenCV frame extraction

### Database Models

**Key Tables**:
1. **accounts** - User accounts (CUID v2 + session UUID)
2. **videos** - Video metadata, analysis status, safety metrics
3. **harmful_events** - Detected incidents with timestamps
4. **analysis_runs** - Analysis execution tracking
5. **transcriptions** - Full text + word timestamps
6. **visual_evidence** - Frame/image evidence
7. **audio_evidence** - Audio snippet evidence
8. **image_labels** - Vision model labels

### Analysis Pipeline Flow

```
1. Video Upload/Download
   ↓
2. Create Analysis Run
   ↓
3. Extract Duration (ffprobe/OpenCV)
   ↓
4. Load/Generate Transcript (WhisperX)
   ↓
5. Generate Segments (transcript + vision)
   ↓
6. Analyze Segments (LLM + vision)
   ↓
7. Build Safety Report (v2 format)
   ↓
8. Persist Results (DB + disk)
   ↓
9. Update Video Metadata
```

### Environment Variables

Key configuration (see `.env.example` for full list):
- `DATABASE_URL` - PostgreSQL connection
- `ANALYSIS_LLM_BACKEND` - LLM routing (http/openrouter/local)
- `ANALYSIS_LLM_HTTP_URL` - vLLM endpoint for SafeLens model
- `OPENROUTER_API_KEY` - API key for external models
- `QWEN_VLLM_BASE_URL` - Vision model endpoint
- `SEGMENTATION_AUTO` - Enable automatic segmentation
- `GPU_MAX_CONCURRENT` - GPU throttling (0=disabled, >0=semaphore)
- `LOG_LEVEL` - Logging level (DEBUG/INFO/WARNING/ERROR/CRITICAL)

---

## Frontend (Next.js)

**Location**: `/home/definevera/Documents/RA/SafeLens/web/frontend/`

### Architecture

**Routing**:
- `/` - Home page (upload + video gallery)
- `/[videoId]` - Video detail page with analysis results
- `/api/*` - Backend proxy routes (no CORS needed)

**State Management**:
- SessionProvider (NextAuth) - Global authentication
- PlayerContext - Video player instance sharing
- Local component state (useState, useRef)
- React Query - Server state caching (not currently used)

### Key Components

**Smart Components**:
- `VideoUpload.tsx` - File/URL upload with validation
- `UserVideos.tsx` - Video gallery with status badges
- `SyncedLyrics.tsx` - Word-level transcription sync
- `ClusteredAnalysisData.tsx` - Event clustering and display

**Presentation Components**:
- `VideoPlayer.tsx` - Video.js integration with markers
- `AnalysisResults.tsx` - Summary display
- `EventExplanation.tsx` - Event detail panel
- `Header.tsx` - Navigation with auth menu

**UI Components** (`components/ui/`):
- Shadcn UI components (Button, Card, Badge, etc.)
- Radix UI primitives
- Tailwind CSS styling

### Advanced Features

**Event Clustering** (`utils/clustering.ts`):
- Time-based gap detection (configurable threshold)
- Confidence filtering
- Category aggregation
- Returns: count, duration, max/avg confidence

**Synced Transcription** (`utils/transcription.ts`):
- Word-level segmentation (max 14 words/line)
- Binary search for O(log n) word lookup
- Gap-based line breaking (0.6s threshold)
- Progressive word highlighting
- Click-to-seek functionality

**Video Markers**:
- Custom HTML markers on progress bar
- Cluster vs single event distinction
- Hover tooltips with confidence/categories
- Seek on click

### API Integration

Frontend proxies all backend calls through Next.js route handlers:

```typescript
// Example: Trigger analysis
POST /api/analyze/[videoId] → Backend POST /api/analyze/{video_id}
Headers: user_id (session UUID)
```

This pattern eliminates CORS complexity and adds authentication headers server-side.

---

## Authentication Service

**Location**: `/home/definevera/Documents/RA/SafeLens/auth-service/`

### OIDC Provider Architecture

**Technology**: Better Auth v1.3.13 with OIDC provider plugin

**Key Features**:
- Full OpenID Connect compliance
- Dynamic client registration (RFC 7591)
- JWT signing with EdDSA (Ed25519)
- Google OAuth integration
- Role-based access control (USER/ADMIN)

### Authentication Flow

```
1. User clicks "Sign In"
   ↓
2. Redirect to auth-service (/sign-in)
   ↓
3. Google OAuth flow
   ↓
4. Auth service creates session
   ↓
5. Callback to frontend (/api/auth/callback/socialai-studio-auth)
   ↓
6. Frontend registers user via POST /api/user/register
   ↓
7. Session established
```

### Database Schema (Drizzle ORM)

**Core Tables**:
1. **users** - User accounts with role (USER/ADMIN)
2. **sessions** - Server-side sessions with IP tracking
3. **accounts** - OAuth provider accounts
4. **verification_tokens** - Email verification
5. **jwks** - JWT signing keys (Ed25519)
6. **oauth_applications** - Registered OIDC clients
7. **oauth_access_tokens** - Issued access tokens
8. **oauth_consents** - User consent records

### OIDC Endpoints

- `/.well-known/openid-configuration` - Discovery
- `/jwks` - Public key set
- `/oauth2/token` - Token endpoint
- `/oauth2/userinfo` - User info
- `/oauth2/register` - Dynamic registration

### Client Registration

**CLI Method**:
```bash
pnpm run register-client -- \
  --name "App Name" \
  --redirect "https://app.example.com/callback" \
  --type web
```

**Admin UI**: http://localhost:3001/admin/apps/new

---

## Database Architecture

### Dual Database Design

**Auth Database** (Port 5433):
- Database: `safelens_auth_db`
- ORM: Drizzle ORM (TypeScript)
- Migrations: Drizzle Kit
- Tables: 8 (users, sessions, accounts, oauth_*, jwks)

**Backend Database** (Port 5432):
- Database: `safelens_web_db`
- ORM: SQLAlchemy 2.0.41 (Python)
- Migrations: Alembic
- Tables: 8 (accounts, videos, harmful_events, transcriptions, etc.)

### Key Relationships

**Backend Database**:
```
accounts (1) ←──→ (N) videos
videos (1) ←──→ (N) harmful_events
videos (1) ←──→ (1) transcriptions
videos (1) ←──→ (N) analysis_runs
harmful_events (1) ←──→ (N) visual_evidence
harmful_events (1) ←──→ (N) audio_evidence
visual_evidence (1) ←──→ (N) image_labels
```

**Foreign Keys**: All use `ON DELETE CASCADE` for referential integrity.

### Migration Management

**Backend (Alembic)**:
```bash
cd web
uv run alembic upgrade head        # Apply migrations
uv run alembic revision --autogenerate -m "description"  # Create migration
uv run alembic downgrade -1        # Rollback one version
```

**Auth Service (Drizzle)**:
```bash
cd auth-service
pnpm run db:generate               # Generate migration
pnpm run db:migrate                # Apply migration
pnpm run db:push                   # Push schema without migration
```

---

## Configuration Management

### Environment Files

**Backend** (`web/.env`):
- Database, LLM routing, vision model config
- Segmentation parameters
- GPU management, logging levels
- CORS settings (disabled by default)

**Frontend** (`web/frontend/.env`):
- Auth.js configuration (client ID/secret, issuer URL)
- Backend URL
- Public app URL

**Auth Service** (`auth-service/.env`):
- Better Auth configuration
- Database URL (separate from backend)
- Google OAuth credentials

### Configuration Patterns

**Python (Dataclass)**:
```python
@dataclass
class SegmentationConfig:
    min_len_sec: float = 5.0
    max_len_sec: float = 16.0

    @classmethod
    def from_env(cls) -> "SegmentationConfig":
        return cls(
            min_len_sec=float(os.getenv("SEG_MIN_LEN_SEC", cls.min_len_sec)),
            # ...
        )
```

**TypeScript (Zod)**:
```typescript
const EnvSchema = z.object({
  AUTH_CLIENT_ID: z.string().min(1),
  AUTH_ISSUER_URL: z.string().url(),
  // ...
});

export const env = EnvSchema.parse({...});
```

### Feature Flags

| Feature | Variable | Values | Default |
|---------|----------|--------|---------|
| Auto Segmentation | `SEGMENTATION_AUTO` | true/false | true |
| Planning Mode | `ANALYSIS_PLANNING_MODE` | segmentation/llm/hybrid | segmentation |
| Suspicion Detection | `SUSPICION_MODE` | keywords/llm/off | llm |
| CORS | `CORS_ENABLED` | true/false | false |
| Metrics | `OBS_METRICS` | true/false | false |
| GPU Throttling | `GPU_MAX_CONCURRENT` | 0-N | 1 |

---

## Video Processing Pipeline

### Upload Flow

**File Upload**:
1. Frontend: User selects file → XHR upload with progress
2. Backend: Validate extension/size → Save to `./videos/{video_id}/video.mp4`
3. Extract thumbnail (frame at t=0)
4. Create video record (status=pending)
5. Return video_id → Frontend navigates to `/[videoId]`

**URL Download**:
1. Frontend: User submits URL → POST /api/upload/url
2. Backend: Validate URL → Create video record (download_status=pending)
3. Background task: yt-dlp download → Extract metadata → Save video
4. Auto-trigger analysis on completion
5. Frontend polls download status

### Analysis Flow

```
1. POST /api/analyze/{video_id}
   → Creates analysis_run (status=processing)
   ↓
2. Load video duration (ffprobe/OpenCV)
   ↓
3. Load/generate transcript (WhisperX)
   ↓
4. Generate segments (transcript + vision)
   ↓
5. Extract frames for each segment
   ↓
6. Analyze frames + transcript via LLM
   ↓
7. Build safety report v2
   ↓
8. Insert harmful_events into DB
   ↓
9. Generate prose summary
   ↓
10. Update video (status=completed, safety_report)
```

### Segmentation Strategy

**Hybrid Approach**:
- Transcript-based: NLTK sentence segmentation
- Visual-based: Vision Transformer scene detection
- Smart merging: Configurable thresholds

**Parameters** (via env vars):
- `SEG_MIN_LEN_SEC` - Minimum segment length (5.0s)
- `SEG_MAX_LEN_SEC` - Maximum segment length (16.0s)
- `SEG_SCENE_THRESHOLD` - Visual similarity threshold (0.85)
- `SEG_SAMPLE_INTERVAL_SEC` - Frame sampling rate (2.0s)

### Frame Extraction

**Methods**:
1. Timestamp-based: Extract specific frames with epsilon retry
2. Interval-based: Every N seconds
3. Range-based: Start/end time with FPS

**Output**: JPEG frames saved as `frame_{ms}.jpg`

### Transcription

**WhisperX Integration**:
- Model: Medium-sized Whisper
- Word-level alignment for precise timestamps
- Device: CUDA (float16) or CPU (int8)
- Caching: Saved to both file and database

---

## API Reference

### Backend Endpoints

**Authentication**:
- `POST /api/auth/register` - Register user

**Video Management**:
- `POST /api/upload` - Upload file
- `POST /api/upload/url` - Download from URL
- `GET /api/user/videos` - List user's videos
- `GET /api/videos/{video_id}` - Get video info
- `GET /api/videos/{video_id}/video.mp4` - Stream video
- `GET /api/videos/{video_id}/thumbnail.jpg` - Get thumbnail

**Analysis**:
- `POST /api/analyze/{video_id}` - Trigger analysis
- `GET /api/analyze/{video_id}/status` - Check progress
- `GET /api/analyze/{video_id}/results` - Get results
- `POST /api/analyze/{video_id}/retry` - Retry failed analysis

**Download Status**:
- `GET /api/download/{video_id}/status` - Check download progress

**Health**:
- `GET /health` - Basic health check
- `GET /health/providers` - Provider readiness

### Frontend API Routes (Proxies)

All routes in `web/frontend/src/app/api/` proxy to backend with authentication:
- Add `user_id` header (session UUID)
- Forward request to backend
- Transform response
- Return to client

**Example**:
```typescript
// Frontend: POST /api/analyze/[videoId]
// → Backend: POST /api/analyze/{video_id}
// Headers: { "user_id": session.user.id }
```

### Request/Response Patterns

**Authentication**: All user-scoped endpoints require `user_id` header (Auth.js session UUID)

**Status Codes**:
- 200 - Success
- 400 - Bad request (validation error)
- 401 - Unauthorized (session not found)
- 404 - Not found
- 409 - Conflict (duplicate, already in progress)
- 500 - Server error

**Safety Report Format (v2)**:
```json
{
  "format_version": 2,
  "video_metadata": {
    "duration": 120.5,
    "safety_rating": "UNSAFE",
    "harmful_events_count": 3,
    "overall_confidence_score": 85.2
  },
  "harmful_events": [
    {
      "timestamp": 45.5,
      "start_time": 45.0,
      "end_time": 50.0,
      "categories": ["violence", "explicit"],
      "confidence_score": 92.1,
      "explanation": "Description of harmful content",
      "verification_source": "vision+audio"
    }
  ],
  "transcription": {
    "full_text": "...",
    "word_timestamps": [...]
  }
}
```

---

## Testing Strategy

### Current Status

**Automated Testing**: Minimal/None
- No pytest, jest, or vitest configured
- No test files or directories
- No CI/CD pipeline

**Quality Gates**:
- TypeScript strict mode (compile-time type checking)
- ESLint for both frontend and auth-service
- Ruff for Python linting

**Manual Testing**:
- Health endpoint verification: `curl localhost:8000/health`
- Linting: `pnpm lint` (frontend/auth), `uv run ruff check` (backend)
- Smoke tests documented in REFACTOR_SPEC.md

### Recommendations for Future Testing

**Backend**:
- Add pytest for API integration tests
- Create `tests/` directory with conftest.py
- Mock vLLM and external services
- Test critical paths: upload, analysis, auth

**Frontend**:
- Add vitest for component testing
- Test clustering and transcription utils
- E2E tests with Playwright

**CI/CD**:
- GitHub Actions workflow
- Run linting + tests on push/PR
- Code coverage reporting

---

## Deployment

### Current Setup: Local Development Only

**No Production Containerization**:
- No Dockerfiles for applications
- No docker-compose.yml
- Databases run in manual Docker containers

### Local Port Mapping

| Service | Port | Purpose |
|---------|------|---------|
| Frontend | 3000 | Next.js UI |
| Auth Service | 3001 | OIDC provider |
| Backend API | 8000 | FastAPI |
| Backend DB | 5432 | PostgreSQL |
| Auth DB | 5433 | PostgreSQL |
| vLLM Llama | 8192 | Text analysis |
| vLLM Qwen | 8193 | Vision captioning |

### Production Considerations

**Required for Production**:
1. Create Dockerfiles for backend, frontend, auth-service
2. Create docker-compose.yml for orchestration
3. Use HTTPS for all services
4. Managed PostgreSQL (AWS RDS, Google Cloud SQL)
5. Secret management (AWS Secrets Manager, etc.)
6. Environment-specific .env files
7. Health checks and readiness probes
8. Log aggregation and monitoring
9. GPU inference strategy (containerize vLLM or use cloud API)

**URL Updates for Production**:
- Change all localhost URLs to production domains
- Update OAuth redirect URIs
- Re-register OIDC clients with production URLs
- Update Google OAuth authorized origins

---

## Key File Locations

### Configuration
- Backend env: `/home/definevera/Documents/RA/SafeLens/web/.env`
- Frontend env: `/home/definevera/Documents/RA/SafeLens/web/frontend/.env`
- Auth env: `/home/definevera/Documents/RA/SafeLens/auth-service/.env`

### Main Entry Points
- Backend: `/home/definevera/Documents/RA/SafeLens/web/server.py`
- Frontend: `/home/definevera/Documents/RA/SafeLens/web/frontend/src/app/layout.tsx`
- Auth: `/home/definevera/Documents/RA/SafeLens/auth-service/src/app/api/auth/[...all]/route.ts`

### Database
- Backend schema: `/home/definevera/Documents/RA/SafeLens/web/database.py`
- Backend migrations: `/home/definevera/Documents/RA/SafeLens/web/alembic/versions/`
- Auth schema: `/home/definevera/Documents/RA/SafeLens/auth-service/src/db/schema.ts`
- Auth migrations: `/home/definevera/Documents/RA/SafeLens/auth-service/src/db/migrations/`

### Core Logic
- Analysis pipeline: `/home/definevera/Documents/RA/SafeLens/web/services/analysis_pipeline.py`
- Video upload: `/home/definevera/Documents/RA/SafeLens/web/routers/videos.py`
- LLM integration: `/home/definevera/Documents/RA/SafeLens/web/tools/llm.py`
- Segmentation: `/home/definevera/Documents/RA/SafeLens/web/app/orchestration/segmentation.py`

### Frontend Components
- Video player: `/home/definevera/Documents/RA/SafeLens/web/frontend/src/components/VideoPlayer.tsx`
- Upload UI: `/home/definevera/Documents/RA/SafeLens/web/frontend/src/components/VideoUpload.tsx`
- Transcription sync: `/home/definevera/Documents/RA/SafeLens/web/frontend/src/components/SyncedLyrics.tsx`
- Clustering: `/home/definevera/Documents/RA/SafeLens/web/frontend/src/utils/clustering.ts`

### Documentation
- Main README: `/home/definevera/Documents/RA/SafeLens/README.md`
- Team guidelines: `/home/definevera/Documents/RA/SafeLens/AGENTS.md`
- Status snapshot: `/home/definevera/Documents/RA/SafeLens/CHECKPOINT.md`
- Refactor spec: `/home/definevera/Documents/RA/SafeLens/REFACTOR_SPEC.md`
- Backend guide: `/home/definevera/Documents/RA/SafeLens/web/README.md`
- Frontend guide: `/home/definevera/Documents/RA/SafeLens/web/frontend/README.md`
- Auth guide: `/home/definevera/Documents/RA/SafeLens/auth-service/README.md`

---

## Development Workflow

### Daily Development

1. **Start databases** (if not running):
   ```bash
   docker start safelens_web_db safelens_auth_db
   ```

2. **Start vLLM** (if doing analysis):
   ```bash
   # Terminal 1: Llama
   CUDA_VISIBLE_DEVICES=0 uvx vllm serve meta-llama/Meta-Llama-3-8B-Instruct \
     --port 8192 --enable-lora --lora-modules SafeLens/llama-3-8b=/path/to/lora

   # Terminal 2: Qwen
   CUDA_VISIBLE_DEVICES=1 uvx vllm serve Qwen/Qwen2.5-VL-7B-Instruct --port 8193
   ```

3. **Start backend**:
   ```bash
   cd web && uv run uvicorn server:app --reload
   ```

4. **Start auth service**:
   ```bash
   cd auth-service && PORT=3001 pnpm dev
   ```

5. **Start frontend**:
   ```bash
   cd web/frontend && pnpm dev
   ```

6. **Access app**: http://localhost:3000

### Code Quality Checks

```bash
# Backend
cd web && uv run ruff check

# Frontend
cd web/frontend && pnpm lint

# Auth service
cd auth-service && pnpm lint
```

### Database Migrations

```bash
# Backend: Create migration
cd web && uv run alembic revision --autogenerate -m "description"

# Backend: Apply migration
uv run alembic upgrade head

# Auth: Generate migration
cd auth-service && pnpm run db:generate

# Auth: Apply migration
pnpm run db:migrate
```

---

## Troubleshooting

### Common Issues

**Database connection errors**:
- Verify Docker containers are running: `docker ps`
- Check DATABASE_URL in .env files
- Ensure ports 5432 and 5433 are available

**vLLM not responding**:
- Check GPU availability: `nvidia-smi`
- Verify CUDA_VISIBLE_DEVICES matches GPU count
- Check vLLM logs for errors
- Test endpoint: `curl localhost:8192/v1/models`

**Frontend auth errors**:
- Verify auth-service is running on port 3001
- Check AUTH_CLIENT_ID/SECRET match registered client
- Verify AUTH_ISSUER_URL points to auth-service
- Check Google OAuth credentials are valid

**Video upload fails**:
- Check file size < 500MB
- Verify file format is supported
- Check backend logs for errors
- Ensure `./videos/` directory is writable

**Analysis stuck in processing**:
- Check vLLM endpoints are accessible
- Verify GPU memory is sufficient
- Check backend logs for errors
- Use retry endpoint: `POST /api/analyze/{video_id}/retry`

---

This guide provides comprehensive information for bootstrapping AI agents and developers working with SafeLens. For specific implementation details, refer to the actual code files and inline documentation.
