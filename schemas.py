from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ScoresModel(BaseModel):
    overall:    int = 0
    discipline: int = 0
    cap_eff:    int = 0
    trade_q:    int = 0
    mkt_align:  int = 0
    vol_handle: int = 0
    peer_cmp:   int = 0

class SessionCreate(BaseModel):
    id:          str
    date:        str
    full:        str
    index_name:  str
    dte:         int = 0
    vix:         Optional[float] = None
    capital:     Optional[float] = None
    gross_pnl:   Optional[float] = None
    net_pnl:     Optional[float] = None
    net_roi:     Optional[float] = None
    gross_roi:   Optional[float] = None
    ce_pnl:      Optional[float] = None
    pe_pnl:      Optional[float] = None
    charges:     Optional[float] = None
    executed:    Optional[int]   = None
    rejected:    Optional[int]   = None
    mt:          Optional[float] = None
    carry_out:   int = 0
    note:        Optional[str]   = None
    peer_rois:   List[float]     = []
    scores:      ScoresModel     = ScoresModel()
    violations:  List[str]       = []
    strengths:   List[str]       = []

class SessionOut(BaseModel):
    id:          str
    date:        str
    full:        str
    index_name:  str
    dte:         int
    vix:         Optional[float]
    capital:     Optional[float]
    gross_pnl:   Optional[float]
    net_pnl:     Optional[float]
    net_roi:     Optional[float]
    gross_roi:   Optional[float]
    ce_pnl:      Optional[float]
    pe_pnl:      Optional[float]
    charges:     Optional[float]
    executed:    Optional[int]
    rejected:    Optional[int]
    mt:          Optional[float]
    carry_out:   int
    note:        Optional[str]
    peer_rois:   List[float]
    scores:      Dict[str, Any]
    violations:  List[str]
    strengths:   List[str]
    ai_commentary: Optional[str]
    csv_filename:  Optional[str]

    class Config:
        from_attributes = True

class TokenRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"

class CSVUploadResult(BaseModel):
    session_id:   str
    gross_pnl:    float
    net_pnl:      float
    net_roi:      float
    ce_pnl:       float
    pe_pnl:       float
    charges_breakdown: Dict[str, float]
    total_charges: float
    executed:     int
    rejected:     int
    strikes:      List[Dict[str, Any]]
    warnings:     List[str]

class AICommentaryRequest(BaseModel):
    session_id: str

class MessageResponse(BaseModel):
    message: str
