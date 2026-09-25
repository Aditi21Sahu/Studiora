# STUDIORA

> **"Everything you need to learn better"**  
> *Learn. Practice. Improve.*

Studiora is an AI-powered learning platform designed for students. It transforms complex study materials (PDFs, Word documents, text notes, and YouTube video lectures) into clear structured notes, interactive multiple-choice quizzes with instant pedagogical feedback and explanations, learning growth tracking, and comprehensive academic performance reports.

---

## 📸 Key Features

- **Fast & Lightweight Architecture**:
  - Pure **HTML5**, **CSS3**, and **Vanilla JavaScript** frontend.
  - Zero heavy JavaScript frameworks (No React, No Next.js, No Node.js, No Vite, No Tailwind CSS).
  - Single-command backend and frontend serving through **FastAPI** & **Uvicorn**.
- **Secure Student Authentication**:
  - Register, Login, and Password Reset workflows.
  - Industry-standard bcrypt password hashing & signed JWT authentication.
- **Multi-Format Study Material Processing**:
  - **PDF Documents**: Direct page and text extraction using `PyMuPDF` (`fitz`) and `pypdf`.
  - **Word Documents (DOCX)**: Structural paragraph and table extraction using `python-docx`.
  - **Video Files (MP4/MKV/MOV/WEBM)**: Audio extraction via FFmpeg and AI transcription using Groq Whisper.
  - **YouTube & Online Video URLs**: Automatic captions extraction via `youtube-transcript-api` with a multi-stage fallback to `yt-dlp` audio download and Groq Whisper transcription.
- **Groq-Powered AI Notes Generation**:
  - Generates structured educational notes with Executive Summaries, Key Takeaways, Formatted Headings, Bullet Points, Vocabulary Definitions, and Rapid Revision Checklists.
  - Download notes in formatted **PDF** (via ReportLab) or clean **TXT** format.
- **Interactive Quizzes**:
  - Generate 5, 10, 15, or 20 multiple-choice questions grounded in the source material across Easy, Medium, and Hard difficulty levels.
  - Interactive test taking with real-time timer, progress bar, and instant pedagogical feedback:
    - Correct answer highlighting in green.
    - Incorrect answer highlighting in red with the correct option identified.
    - Clear AI-grounded educational explanation detailing *why* the answer is correct.
- **25-Mark Timed Examination Test Papers**:
  - Full-length structured examination papers simulating authentic school and competitive exams.
  - Exactly 20 questions totaling 25 marks across 3 structured sections:
    - **Section A**: 10 Multiple-Choice Questions (10 Marks).
    - **Section B**: 6 Short Answer Conceptual Questions (6 Marks).
    - **Section C**: 3 Long Answer Explanatory Questions (9 Marks).
  - 30-minute real-time countdown timer, autosave draft persistence, question navigation palette, and automated evaluation with model answers.
- **Cloud-Ready YouTube Ingestion**:
  - Uses **Supadata AI Transcript API** with canonical URL resolution to bypass YouTube datacenter anti-bot IP blocks on cloud hosts like Render.
  - Graceful multi-tier fallback to `youtube-transcript-api`, Innertube Android Client, in-memory `yt-dlp` subtitle extraction, and Groq Whisper STT for local development.
- **Comprehensive Results & Learning Growth**:
  - Final score percentage and correct/incorrect counters.
  - Interactive HTML5 canvas learning growth chart tracking score progression over time.
  - Recent activity timeline and historical quiz attempt review with question-by-question breakdown.

---

## 🎨 Brand Design System & Colors

Studiora follows a clean, modern EdTech design system with soft lavender backgrounds and rich purple accents:

| Color Name | Hex Code | Purpose |
| :--- | :--- | :--- |
| **PRIMARY PURPLE** | `#7C5CFF` | Primary actions, brand accents, active states |
| **DARK PURPLE** | `#5B2BE0` | Button hover states, emphasized headers |
| **LIGHT PURPLE** | `#EEE9FF` | Sidebar active background, badge containers |
| **VERY LIGHT PURPLE** | `#F7F4FF` | Hero background, card highlights |
| **MAIN BACKGROUND** | `#FAF9FF` | Global application page background |
| **PRIMARY TEXT** | `#29234A` | Headings, card titles, prominent text |
| **SECONDARY TEXT** | `#716B89` | Body text, labels, metadata |
| **BORDER COLOR** | `#E5E0F5` | Clean structural dividers and borders |
| **SUCCESS** | `#22B573` | Correct answers, positive alerts (`#E9F9F1` bg) |
| **ERROR** | `#E54861` | Incorrect answers, danger actions (`#FFF0F2` bg) |
| **WARNING** | `#F4A340` | Processing states (`#FFF6E7` bg) |
| **INFO** | `#4B8DF8` | Informational badges (`#EEF5FF` bg) |

**Typography**:
- **Poppins** (`Google Fonts`): Brand name, major headings, card titles, CTA buttons.
- **Inter** (`Google Fonts`): Body content, forms, notes, quiz questions, tables, statistics.

---

## 🛠️ Technology Stack

- **Frontend**:
  - HTML5 & CSS3
  - Vanilla JavaScript (ES6+)
  - Google Fonts (Poppins & Inter)
- **Backend**:
  - Python 3.13 (pinned for cloud deployments)
  - FastAPI & Uvicorn ASGI
  - SQLAlchemy ORM
  - SQLite Database (`studiora.db`)
  - Passlib & Bcrypt (Password Hashing)
  - Python-Jose (JWT Authentication)
  - Groq Python SDK (`llama-3.3-70b-versatile` & `whisper-large-v3-turbo`)
  - Supadata AI Transcript API (Cloud YouTube Ingestion)
  - PyMuPDF (`fitz`), Python-Docx & ReportLab

---

## 📁 Project Structure

```
studiora/
├── frontend/
│   ├── assets/               # Brand logo & student illustrations
│   ├── css/
│   │   └── style.css         # Master Studiora stylesheet (lavender theme & Poppins)
│   ├── js/
│   │   ├── api.js            # Centralized API fetch client with JWT token auth
│   │   ├── layout.js         # Sidebar, header, navigation & toast notifications
│   │   ├── auth.js           # Login, registration & password reset
│   │   ├── dashboard.js      # Dashboard stats, activity & HTML5 canvas growth chart
│   │   ├── material.js       # Drag & drop upload, YouTube URL processing & previews
│   │   ├── notes.js          # Notes library, reader modal & PDF/TXT downloads
│   │   ├── quiz.js           # Quiz generator, interactive runner & scoring
│   │   ├── test-paper.js     # 25-mark timed exam runner, autosave & review
│   │   └── reports.js        # Analytics summary & past attempt breakdown
│   ├── index.html            # Landing page with hero & feature highlights
│   ├── login.html            # User login
│   ├── register.html         # User registration
│   ├── forgot-password.html  # Password reset
│   ├── dashboard.html        # Main student workspace dashboard
│   ├── study-material.html   # Upload documents & video links
│   ├── notes.html            # Structured study notes
│   ├── quizzes.html          # Interactive practice tests
│   ├── test-papers.html      # 25-mark timed exam simulator
│   └── reports.html          # Growth analytics & performance review
│
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point, static frontend mount & CORS
│   │   ├── database.py       # SQLite connection & session
│   │   ├── config.py         # Settings & environment configuration
│   │   ├── models/           # User, Material, Note, Quiz, Attempt, TestPaper, Activity
│   │   ├── schemas/          # Pydantic request & response models
│   │   ├── services/         # TranscriptService, Notes, Quiz, Test, Document, Auth
│   │   └── routes/           # Modular API routers (/api/materials, /api/tests, etc.)
│   ├── uploads/              # Local file uploads directory
│   ├── .env.example          # Environment variables template
│   ├── requirements.txt      # Python dependencies (pinned for Python 3.13)
│   ├── studiora.db           # SQLite database
│   └── main.py               # Render root deployment entry-point
│
├── render.yaml               # Infrastructure-as-code for Render deployment
├── .python-version           # Pinned to 3.13
├── README.md
├── .gitignore
└── LICENSE
```

---

## 🚀 Running the Web Application

### 1. Prerequisites
- **Python 3.10+** (verify with `python --version` or `py -3.10 --version`)
- **FFmpeg** (installed and available on your system PATH for audio/video transcription)

---

### 2. Quick Start (Single Command)

1. Open a terminal and navigate to the `backend/` directory:
   ```bash
   cd backend
   ```

2. Activate the virtual environment:
   - **Windows (PowerShell)**:
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux**:
     ```bash
     source venv/bin/activate
     ```

3. Ensure dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure your `.env` file:
   Ensure `backend/.env` contains your API keys:
   ```ini
   GROQ_API_KEY=your_actual_groq_api_key_here
   YOUTUBE_TRANSCRIPT_API_KEY=your_actual_supadata_api_key_here
   GROQ_TEXT_MODEL=llama-3.3-70b-versatile
   GROQ_STT_MODEL=whisper-large-v3-turbo
   DATABASE_URL=sqlite:///./studiora.db
   JWT_SECRET_KEY=studiora_super_secret_jwt_key_2026_safe_dev_production
   FRONTEND_URL=http://localhost:8000
   ```

5. Run the integration test suite to verify everything works:
   ```bash
   python test_backend.py
   ```

6. Start the unified server:
   ```bash
   uvicorn app.main:app --port 8000 --reload
   ```

7. Open your web browser and go to:
   ```
   http://localhost:8000
   ```

That's it! Both the frontend and backend are completely served from `http://localhost:8000`.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
