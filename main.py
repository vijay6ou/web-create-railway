"""
VJ Trading Dashboard — FastAPI Backend
Deploy to Railway. Serves as the persistent data layer
for the Firebase-hosted frontend.
"""
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session as DBSession
import json
import os

from database import engine, get_db, Base
from models import Session as SessionModel
from schemas import (
    SessionCreate, SessionOut, TokenRequest, TokenResponse,
    CSVUploadResult, AICommentaryRequest, MessageResponse
)
from auth import authenticate_user, create_access_token, get_current_user, require_admin
from csv_parser import parse_orderbook_csv
from seed import seed

# ── Create all tables + seed on startup ──
Base.metadata.create_all(bind=engine)
seed()

app = FastAPI(
    title="VJ Trading Dashboard API",
    description="Backend for VJ Trading Dashboard — Indian Index Options Performance Tracker",
    version="1.0.0"
)

# ── CORS: Allow Firebase frontend + localhost for dev ──
ALLOWED_ORIGINS = [
    "https://vj-trading-data.web.app",
    "https://vj-trading-data.firebaseapp.com",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:5500",  # VS Code Live Server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ════════════════════════════════════════
#  HEALTH CHECK
# ════════════════════════════════════════

@app.get("/", tags=["Health"])
def root():
    return {"status": "VJ Trading API is running", "version": "1.0.0"}

@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


# ════════════════════════════════════════
#  AUTH
# ════════════════════════════════════════

@app.post("/auth/token", response_model=TokenResponse, tags=["Auth"])
def login(body: TokenRequest):
    """Login with username + password. Returns JWT token valid for 7 days."""
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return {"access_token": token}

@app.get("/auth/me", tags=["Auth"])
def get_me(user: dict = Depends(get_current_user)):
    return {"username": user["username"], "role": user["role"]}


# ════════════════════════════════════════
#  SESSIONS — GET ALL
# ════════════════════════════════════════

@app.get("/sessions", tags=["Sessions"])
def get_sessions(
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Fetch all sessions ordered by date. Returns frontend-ready JSON."""
    rows = db.query(SessionModel).order_by(SessionModel.id).all()
    
    result = []
    for r in rows:
        result.append({
            "id":          r.id,
            "date":        r.date,
            "full":        r.full,
            "index":       r.index_name,
            "dte":         r.dte,
            "vix":         r.vix,
            "capital":     r.capital,
            "gross_pnl":   r.gross_pnl,
            "net_pnl":     r.net_pnl,
            "net_roi":     r.net_roi,
            "gross_roi":   r.gross_roi,
            "ce_pnl":      r.ce_pnl,
            "pe_pnl":      r.pe_pnl,
            "charges":     r.charges,
            "executed":    r.executed,
            "rejected":    r.rejected,
            "mt":          r.mt,
            "carry_out":   r.carry_out,
            "note":        r.note,
            "peer_rois":   json.loads(r.peer_rois_json or "[]"),
            "scores":      json.loads(r.scores_json or "{}"),
            "violations":  json.loads(r.violations_json or "[]"),
            "strengths":   json.loads(r.strengths_json or "[]"),
            "ai_commentary": r.ai_commentary,
            "csv_filename":  r.csv_filename
        })
    return result


# ════════════════════════════════════════
#  SESSIONS — GET ONE
# ════════════════════════════════════════

@app.get("/sessions/{session_id}", tags=["Sessions"])
def get_session(
    session_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    row = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": row.id, "date": row.date, "full": row.full,
        "index": row.index_name, "vix": row.vix, "capital": row.capital,
        "gross_pnl": row.gross_pnl, "net_pnl": row.net_pnl,
        "net_roi": row.net_roi, "charges": row.charges,
        "ce_pnl": row.ce_pnl, "pe_pnl": row.pe_pnl,
        "executed": row.executed, "rejected": row.rejected,
        "mt": row.mt, "carry_out": row.carry_out,
        "note": row.note,
        "peer_rois":  json.loads(row.peer_rois_json or "[]"),
        "scores":     json.loads(row.scores_json or "{}"),
        "violations": json.loads(row.violations_json or "[]"),
        "strengths":  json.loads(row.strengths_json or "[]"),
        "ai_commentary": row.ai_commentary,
        "csv_filename":  row.csv_filename
    }


# ════════════════════════════════════════
#  SESSIONS — CREATE / UPDATE
# ════════════════════════════════════════

@app.post("/sessions", tags=["Sessions"])
def create_or_update_session(
    body: SessionCreate,
    db: DBSession = Depends(get_db),
    user: dict = Depends(require_admin)
):
    """Create or update a session. Admin only. Upsert by session id (date)."""
    existing = db.query(SessionModel).filter(SessionModel.id == body.id).first()

    data = {
        "id":          body.id,
        "date":        body.date,
        "full":        body.full,
        "index_name":  body.index_name,
        "dte":         body.dte,
        "vix":         body.vix,
        "capital":     body.capital,
        "gross_pnl":   body.gross_pnl,
        "net_pnl":     body.net_pnl,
        "net_roi":     body.net_roi,
        "gross_roi":   body.gross_roi,
        "ce_pnl":      body.ce_pnl,
        "pe_pnl":      body.pe_pnl,
        "charges":     body.charges,
        "executed":    body.executed,
        "rejected":    body.rejected,
        "mt":          body.mt,
        "carry_out":   body.carry_out,
        "note":        body.note,
        "peer_rois_json":   json.dumps(body.peer_rois),
        "scores_json":      json.dumps(body.scores.dict()),
        "violations_json":  json.dumps(body.violations),
        "strengths_json":   json.dumps(body.strengths),
    }

    if existing:
        for k, v in data.items():
            setattr(existing, k, v)
        db.commit()
        return {"message": "Session updated", "id": body.id}
    else:
        obj = SessionModel(**data)
        db.add(obj)
        db.commit()
        return {"message": "Session created", "id": body.id}


# ════════════════════════════════════════
#  SESSIONS — DELETE
# ════════════════════════════════════════

@app.delete("/sessions/{session_id}", tags=["Sessions"])
def delete_session(
    session_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(require_admin)
):
    row = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(row)
    db.commit()
    return {"message": f"Session {session_id} deleted"}


# ════════════════════════════════════════
#  CSV UPLOAD & AUTO-PARSE
# ════════════════════════════════════════

@app.post("/upload-csv/{session_id}", tags=["CSV"])
async def upload_csv(
    session_id: str,
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db),
    user: dict = Depends(require_admin)
):
    """
    Upload STOXXO order book CSV for a session.
    Parses it server-side, computes all charges and P&L,
    and stores both the raw CSV and computed results.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    content = await file.read()
    csv_text = content.decode('utf-8', errors='replace')

    # Parse
    result = parse_orderbook_csv(csv_text)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    # Store CSV + computed data on session
    row = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not row:
        # Auto-create minimal session record if not exists
        row = SessionModel(id=session_id, date=session_id, full=session_id, index_name=result["index_name"])
        db.add(row)

    row.csv_data     = csv_text
    row.csv_filename = file.filename
    row.gross_pnl    = result["gross_pnl"]
    row.net_pnl      = result["net_pnl"]
    row.ce_pnl       = result["ce_pnl"]
    row.pe_pnl       = result["pe_pnl"]
    row.charges      = result["total_charges"]
    row.executed     = result["executed"]
    row.rejected     = result["rejected"]
    row.index_name   = result["index_name"]

    if row.capital and row.capital > 0:
        row.net_roi   = round(result["net_pnl"]   / row.capital * 100, 4)
        row.gross_roi = round(result["gross_pnl"] / row.capital * 100, 4)

    db.commit()

    return {
        "session_id":        session_id,
        "gross_pnl":         result["gross_pnl"],
        "net_pnl":           result["net_pnl"],
        "ce_pnl":            result["ce_pnl"],
        "pe_pnl":            result["pe_pnl"],
        "charges_breakdown": result["charges_breakdown"],
        "total_charges":     result["total_charges"],
        "executed":          result["executed"],
        "rejected":          result["rejected"],
        "strikes":           result["strikes"],
        "carry_positions":   result["carry_positions"],
        "warnings":          result["warnings"],
        "message":           f"Parsed {result['executed']} orders, {len(result['strikes'])} strikes"
    }


# ════════════════════════════════════════
#  AI COMMENTARY (Claude API)
# ════════════════════════════════════════

@app.post("/ai-commentary/{session_id}", tags=["AI"])
async def generate_ai_commentary(
    session_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(require_admin)
):
    """
    Generate AI commentary for a session using Claude API.
    On-demand only — not auto-generated. Stored in DB after generation.
    Requires ANTHROPIC_API_KEY environment variable.
    """
    import httpx

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")

    row = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    scores = json.loads(row.scores_json or "{}")
    violations = json.loads(row.violations_json or "[]")
    strengths = json.loads(row.strengths_json or "[]")

    prompt = f"""You are an expert Indian index options trading coach analyzing a session by Vijay, a senior systematic options seller.

SESSION: {row.full} — {row.index_name} Expiry
VIX: {row.vix} | Capital: ₹{(row.capital or 0)/1e7:.2f} Cr | Market Toughness: {row.mt}/10

P&L:
- Gross: ₹{(row.gross_pnl or 0):,.0f} | Net: ₹{(row.net_pnl or 0):,.0f} | Net ROI: {row.net_roi or 0:.3f}%
- CE P&L: ₹{(row.ce_pnl or 0):,.0f} | PE P&L: ₹{(row.pe_pnl or 0):,.0f}
- Charges: ₹{(row.charges or 0):,.0f} | Executed: {row.executed} | Rejected: {row.rejected}

Scores: {scores}

Violations:
{chr(10).join(f'- {v}' for v in violations)}

Strengths:
{chr(10).join(f'- {s}' for s in strengths)}

Provide a sharp, specific 3-paragraph commentary:
1. What the session score tells us — where the P&L came from, what the charges-to-gross ratio means
2. The single most important pattern to fix before next expiry (be direct, name the specific rule violated)
3. One specific adjustment for the next session setup — concrete strike placement guidance

Be direct. No generic advice. Reference the specific numbers."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 600,
                "messages": [{"role": "user", "content": prompt}]
            }
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Claude API error: {resp.text}")

    commentary = resp.json()["content"][0]["text"]
    row.ai_commentary = commentary
    db.commit()

    return {"session_id": session_id, "commentary": commentary}
