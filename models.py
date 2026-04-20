from sqlalchemy import Column, String, Float, Integer, Text, DateTime, Boolean
from sqlalchemy.sql import func
from database import Base
import json

class Session(Base):
    __tablename__ = "sessions"

    id           = Column(String, primary_key=True, index=True)  # "2026-04-16"
    date         = Column(String)          # "Apr 16"
    full         = Column(String)          # "16-Apr-2026"
    index_name   = Column(String)          # "Nifty" / "BankNifty" / "Sensex"
    dte          = Column(Integer, default=0)
    vix          = Column(Float, nullable=True)
    capital      = Column(Float, nullable=True)

    gross_pnl    = Column(Float, nullable=True)
    net_pnl      = Column(Float, nullable=True)
    net_roi      = Column(Float, nullable=True)
    gross_roi    = Column(Float, nullable=True)
    ce_pnl       = Column(Float, nullable=True)
    pe_pnl       = Column(Float, nullable=True)
    charges      = Column(Float, nullable=True)
    executed     = Column(Integer, nullable=True)
    rejected     = Column(Integer, nullable=True)
    mt           = Column(Float, nullable=True)
    carry_out    = Column(Integer, default=0)
    note         = Column(Text, nullable=True)

    # JSON fields stored as text
    peer_rois_json    = Column(Text, default="[]")
    scores_json       = Column(Text, default="{}")
    violations_json   = Column(Text, default="[]")
    strengths_json    = Column(Text, default="[]")

    # File attachment (order book CSV stored as text)
    csv_data     = Column(Text, nullable=True)
    csv_filename = Column(String, nullable=True)

    # AI commentary
    ai_commentary = Column(Text, nullable=True)

    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())

    # Helpers
    @property
    def peer_rois(self):
        return json.loads(self.peer_rois_json or "[]")

    @property
    def scores(self):
        return json.loads(self.scores_json or "{}")

    @property
    def violations(self):
        return json.loads(self.violations_json or "[]")

    @property
    def strengths(self):
        return json.loads(self.strengths_json or "[]")
