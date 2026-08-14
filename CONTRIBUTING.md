# Contributing to SQUARE 🚀

Thank you for your interest in contributing to **SQUARE** (Enterprise Agent Engineering Platform)! We welcome contributions from developers, researchers, and open-source enthusiasts.

---

## 🌟 How Can You Contribute?

You can contribute to SQUARE in several ways:
- **Reporting Bugs**: File detailed bug reports via GitHub Issues.
- **Suggesting Features**: Propose new agent templates, simulation scenarios, or UI components.
- **Code Contributions**: Fix issues, optimize LLM prompts, add vector search capabilities, or improve test coverage.
- **Documentation**: Improve setup guides, architectural diagrams, or inline code docs.

---

## 🛠️ Local Development Setup

### Prerequisites
- **Python**: 3.11 or higher
- **Node.js**: v18 or higher (v20 recommended)
- **Git**

### 1. Fork & Clone
```bash
git clone https://github.com/YOUR-USERNAME/SQUARE.git
cd SQUARE
```

### 2. Backend Setup (FastAPI)
```bash
cd backend

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables template
cp .env.example .env

# Edit .env and provide your GROQ_API_KEY
```

Run backend server:
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Swagger API docs will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 3. Frontend Setup (Next.js 14)
In a new terminal:
```bash
cd frontend

# Install packages
npm install

# Start development server
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🔄 Development Workflow

1. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/amazing-new-feature
   ```

2. **Make Your Changes**:
   - Ensure your code follows PEP 8 for Python and ESLint formatting for TypeScript/React.
   - Test your changes thoroughly against local backend APIs and frontend flows.

3. **Commit Your Changes**:
   ```bash
   git commit -m "feat(simulation): add unexpected API latency scenario"
   ```

4. **Push & Create a Pull Request**:
   ```bash
   git push origin feature/amazing-new-feature
   ```
   Open a Pull Request on GitHub against the `main` branch with a clear description of your changes.

---

## 📜 Code of Conduct

Please be respectful and welcoming to all contributors. We aim to foster an inclusive, constructive open-source community.

Happy coding! 🤖
