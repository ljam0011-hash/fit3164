from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, JSON, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func
import secrets
import hashlib
import json
from collections import defaultdict
import uvicorn
import csv
import io
from enum import Enum

# Database setup
import os
SQLALCHEMY_DATABASE_URL = "sqlite:///./voting_system.db"

# Delete old database if it exists to ensure clean schema
if os.path.exists("voting_system.db"):
    print("⚠️  Existing database found. Deleting to ensure clean schema...")
    os.remove("voting_system.db")
    print("✅ Old database removed.")

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Fix for SQLAlchemy 2.0 deprecation warning
from sqlalchemy.orm import declarative_base
Base = declarative_base()

# FastAPI app
app = FastAPI(title="Monash Club Electronic Voting System", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Enums
class AuditActionType(str, Enum):
    CREATE_ELECTION = "create_election"
    UPDATE_ELECTION = "update_election"
    DELETE_ELECTION = "delete_election"
    ADD_CANDIDATE = "add_candidate"
    REMOVE_CANDIDATE = "remove_candidate"
    BULK_IMPORT_CANDIDATES = "bulk_import_candidates"
    CREATE_TEMPLATE = "create_template"
    USE_TEMPLATE = "use_template"
    FREEZE_ELECTION = "freeze_election"
    UNFREEZE_ELECTION = "unfreeze_election"
    EXPORT_RESULTS = "export_results"
    VIEW_AUDIT_LOG = "view_audit_log"

# Database Models
class Election(Base):
    __tablename__ = "elections"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_frozen = Column(Boolean, default=False)
    template_id = Column(Integer, ForeignKey("election_templates.id"), nullable=True)
    
    candidates = relationship("Candidate", back_populates="election", cascade="all, delete-orphan")
    voting_sessions = relationship("VotingSession", back_populates="election")
    template = relationship("ElectionTemplate", back_populates="elections")
    audit_logs = relationship("AuditLog", back_populates="election")

class ElectionTemplate(Base):
    __tablename__ = "election_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String)
    config = Column(JSON)  # Stores election configuration
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String)
    
    elections = relationship("Election", back_populates="template")

class Candidate(Base):
    __tablename__ = "candidates"
    
    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(Integer, ForeignKey("elections.id"))
    name = Column(String, nullable=False)
    faculty = Column(String)
    manifesto = Column(String)
    external_id = Column(String)  # For bulk import tracking
    
    election = relationship("Election", back_populates="candidates")

class Voter(Base):
    __tablename__ = "voters"
    
    id = Column(Integer, primary_key=True, index=True)
    google_id = Column(String, unique=True, index=True)  # Google user ID
    email = Column(String, index=True)  # Google email
    pseudonym_id = Column(String, unique=True, index=True)  # Hashed identifier
    faculty = Column(String)
    gender = Column(String)
    study_level = Column(String)
    year_level = Column(Integer)
    
    voting_sessions = relationship("VotingSession", back_populates="voter")

class VotingSession(Base):
    __tablename__ = "voting_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(String, unique=True, index=True)
    confirmation_code = Column(String, unique=True, index=True)  # Short code for verification
    voter_id = Column(Integer, ForeignKey("voters.id"))
    election_id = Column(Integer, ForeignKey("elections.id"))
    voted_at = Column(DateTime)
    is_used = Column(Boolean, default=False)
    
    voter = relationship("Voter", back_populates="voting_sessions")
    election = relationship("Election", back_populates="voting_sessions")
    votes = relationship("Vote", back_populates="voting_session")
    vote_receipts = relationship("VoteReceipt", back_populates="voting_session")

class Vote(Base):
    __tablename__ = "votes"
    
    id = Column(Integer, primary_key=True, index=True)
    voting_session_id = Column(Integer, ForeignKey("voting_sessions.id"))
    preferences = Column(JSON)  # Stores ranked preferences as JSON
    submitted_at = Column(DateTime, default=datetime.utcnow)
    vote_hash = Column(String)  # Hash of vote for integrity verification
    
    voting_session = relationship("VotingSession", back_populates="votes")

class VoteReceipt(Base):
    __tablename__ = "vote_receipts"
    
    id = Column(Integer, primary_key=True, index=True)
    voting_session_id = Column(Integer, ForeignKey("voting_sessions.id"))
    receipt_number = Column(String, unique=True, index=True)
    receipt_content = Column(Text)  # HTML/PDF content
    generated_at = Column(DateTime, default=datetime.utcnow)
    
    voting_session = relationship("VotingSession", back_populates="vote_receipts")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    action_type = Column(String, nullable=False)
    actor_id = Column(String, nullable=False)  # Google ID or admin identifier
    actor_email = Column(String)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=True)
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String)
    
    election = relationship("Election", back_populates="audit_logs")

# Create tables
print("📊 Creating database tables...")
Base.metadata.create_all(bind=engine)
print("✅ Database tables created successfully!")

# Pydantic models
class ElectionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    template_id: Optional[int] = None

class ElectionTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    config: Dict[str, Any]

class CandidateCreate(BaseModel):
    name: str
    faculty: Optional[str] = None
    manifesto: Optional[str] = None
    external_id: Optional[str] = None

class CandidateBulkImport(BaseModel):
    candidates: List[CandidateCreate]

class VoterTraits(BaseModel):
    faculty: str
    gender: str
    study_level: str
    year_level: int

class GoogleUserInfo(BaseModel):
    id: str  # Google unique user ID
    email: EmailStr
    name: Optional[str] = None
    picture: Optional[str] = None

class BallotSubmission(BaseModel):
    google_user_info: GoogleUserInfo  # Now includes Google user data
    election_id: int
    preferences: Dict[int, int]  # candidate_id: preference_rank
    voter_traits: VoterTraits
    
    @field_validator('google_user_info')
    @classmethod
    def validate_monash_email(cls, v):
        if not v.email.endswith('@student.monash.edu'):
            raise ValueError('Must be a valid @student.monash.edu email address')
        return v
    
    @field_validator('preferences')
    @classmethod
    def validate_preferences(cls, v):
        ranks = list(v.values())
        if sorted(ranks) != list(range(1, len(ranks) + 1)):
            raise ValueError('Preferences must be a complete ranking starting from 1')
        return v

class VoteVerification(BaseModel):
    confirmation_code: str
    google_id: Optional[str] = None  # Optional additional verification

class ElectionResults(BaseModel):
    election_id: int
    title: str
    total_votes: int
    turnout_by_faculty: Dict[str, int]
    turnout_by_gender: Dict[str, int]
    turnout_by_study_level: Dict[str, int]
    vote_counts: Dict[str, int]  # For first preferences
    status: str

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper functions
def generate_session_token():
    """Generate a cryptographically secure session token"""
    return secrets.token_urlsafe(32)

def generate_confirmation_code():
    """Generate a short confirmation code for vote verification"""
    return secrets.token_hex(4).upper()

def generate_receipt_number():
    """Generate a unique receipt number"""
    return f"RCP-{secrets.token_hex(6).upper()}"

def generate_pseudonym(google_id: str, email: str):
    """Generate a pseudonymous ID from Google ID and email"""
    combined = f"{google_id}:{email}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16]

def generate_vote_hash(preferences: dict, voter_id: int, election_id: int):
    """Generate a hash of the vote for integrity verification"""
    vote_data = f"{json.dumps(preferences, sort_keys=True)}:{voter_id}:{election_id}"
    return hashlib.sha256(vote_data.encode()).hexdigest()

def log_audit_action(
    db: Session,
    action_type: AuditActionType,
    actor_id: str,
    actor_email: str = None,
    election_id: int = None,
    details: dict = None,
    ip_address: str = None
):
    """Log an administrative action to the audit trail"""
    audit_log = AuditLog(
        action_type=action_type.value,
        actor_id=actor_id,
        actor_email=actor_email,
        election_id=election_id,
        details=details or {},
        ip_address=ip_address
    )
    db.add(audit_log)
    db.commit()
    return audit_log

def generate_vote_receipt_html(
    voter_name: str,
    election_title: str,
    confirmation_code: str,
    receipt_number: str,
    voted_at: datetime,
    candidates: List[str]
) -> str:
    """Generate HTML receipt for vote"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Vote Receipt</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; }}
            .header {{ background-color: #4285f4; color: white; padding: 20px; text-align: center; }}
            .receipt-info {{ background-color: #f0f0f0; padding: 15px; margin: 20px 0; }}
            .confirmation {{ font-size: 24px; font-weight: bold; color: #4285f4; text-align: center; padding: 20px; }}
            .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Official Vote Receipt</h1>
            <p>Monash Club Electronic Voting System</p>
        </div>
        
        <div class="receipt-info">
            <p><strong>Receipt Number:</strong> {receipt_number}</p>
            <p><strong>Voter:</strong> {voter_name}</p>
            <p><strong>Election:</strong> {election_title}</p>
            <p><strong>Date & Time:</strong> {voted_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
        
        <div class="confirmation">
            <p>Confirmation Code</p>
            <p>{confirmation_code}</p>
        </div>
        
        <p><strong>Important:</strong> Your vote has been securely recorded. Keep this receipt for your records. 
        You can verify your vote was counted using the confirmation code above.</p>
        
        <p><strong>Privacy Notice:</strong> Your actual vote preferences are not shown on this receipt to maintain 
        ballot secrecy. Only you know how you voted.</p>
        
        <div class="footer">
            <p>This is an official receipt from the Monash Club Electronic Voting System.</p>
            <p>For vote verification, visit: /api/verify-vote</p>
        </div>
    </body>
    </html>
    """
    return html

def calculate_irv_winner(db: Session, election_id: int):
    """Calculate winner using Instant Runoff Voting"""
    votes = db.query(Vote).join(VotingSession).filter(
        VotingSession.election_id == election_id
    ).all()
    
    if not votes:
        return None
    
    # Get all candidates
    candidates = db.query(Candidate).filter(Candidate.election_id == election_id).all()
    candidate_ids = [c.id for c in candidates]
    
    # Parse all ballots
    ballots = []
    for vote in votes:
        preferences = vote.preferences
        sorted_prefs = sorted(preferences.items(), key=lambda x: x[1])
        ballot = [int(cand_id) for cand_id, _ in sorted_prefs]
        ballots.append(ballot)
    
    # IRV algorithm
    while True:
        # Count first preferences
        first_pref_counts = defaultdict(int)
        for ballot in ballots:
            if ballot:
                first_pref_counts[ballot[0]] += 1
        
        total_votes = len(ballots)
        
        # Check for majority winner
        for candidate, count in first_pref_counts.items():
            if count > total_votes / 2:
                return candidate
        
        # Find candidate with fewest votes
        min_votes = min(first_pref_counts.values()) if first_pref_counts else 0
        candidates_to_eliminate = [c for c, v in first_pref_counts.items() if v == min_votes]
        
        if len(candidates_to_eliminate) == len(first_pref_counts):
            # Tie between all remaining candidates
            return list(first_pref_counts.keys())[0] if first_pref_counts else None
        
        # Eliminate candidate(s)
        for candidate in candidates_to_eliminate:
            ballots = [[c for c in ballot if c != candidate] for ballot in ballots]
        
        # Remove empty ballots
        ballots = [b for b in ballots if b]
        
        if not ballots:
            return None

# API Endpoints

@app.get("/")
async def root():
    return {"message": "Monash Club Electronic Voting System API", "version": "2.0.0"}

# Election Management Endpoints
@app.post("/api/elections", response_model=dict)
async def create_election(
    election: ElectionCreate,
    admin_id: str = "admin",  # In production, get from auth
    admin_email: str = "admin@monash.edu",
    db: Session = Depends(get_db)
):
    """Create a new election (Admin only)"""
    db_election = Election(**election.dict())
    
    # If using a template, load configuration
    if election.template_id:
        template = db.query(ElectionTemplate).filter(ElectionTemplate.id == election.template_id).first()
        if template:
            # Apply template configuration
            config = template.config
            if "default_candidates" in config:
                # Will be handled separately
                pass
    
    db.add(db_election)
    db.commit()
    db.refresh(db_election)
    
    # Log audit action
    log_audit_action(
        db=db,
        action_type=AuditActionType.CREATE_ELECTION,
        actor_id=admin_id,
        actor_email=admin_email,
        election_id=db_election.id,
        details={"title": db_election.title, "template_used": election.template_id}
    )
    
    return {"message": "Election created successfully", "election_id": db_election.id}

@app.post("/api/elections/{election_id}/candidates", response_model=dict)
async def add_candidate(
    election_id: int,
    candidate: CandidateCreate,
    admin_id: str = "admin",
    admin_email: str = "admin@monash.edu",
    db: Session = Depends(get_db)
):
    """Add a candidate to an election"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    
    if election.is_frozen:
        raise HTTPException(status_code=400, detail="Election is frozen")
    
    db_candidate = Candidate(election_id=election_id, **candidate.dict())
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    
    # Log audit action
    log_audit_action(
        db=db,
        action_type=AuditActionType.ADD_CANDIDATE,
        actor_id=admin_id,
        actor_email=admin_email,
        election_id=election_id,
        details={"candidate_name": candidate.name, "candidate_id": db_candidate.id}
    )
    
    return {"message": "Candidate added successfully", "candidate_id": db_candidate.id}

@app.post("/api/elections/{election_id}/candidates/bulk", response_model=dict)
async def bulk_import_candidates(
    election_id: int,
    candidates: CandidateBulkImport,
    admin_id: str = "admin",
    admin_email: str = "admin@monash.edu",
    db: Session = Depends(get_db)
):
    """Bulk import candidates via JSON"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    
    if election.is_frozen:
        raise HTTPException(status_code=400, detail="Election is frozen")
    
    added_candidates = []
    for candidate_data in candidates.candidates:
        db_candidate = Candidate(election_id=election_id, **candidate_data.dict())
        db.add(db_candidate)
        added_candidates.append(db_candidate)
    
    db.commit()
    
    # Log audit action
    log_audit_action(
        db=db,
        action_type=AuditActionType.BULK_IMPORT_CANDIDATES,
        actor_id=admin_id,
        actor_email=admin_email,
        election_id=election_id,
        details={"count": len(added_candidates), "candidates": [c.name for c in added_candidates]}
    )
    
    return {
        "message": f"Successfully imported {len(added_candidates)} candidates",
        "candidate_ids": [c.id for c in added_candidates]
    }

@app.post("/api/elections/{election_id}/candidates/csv", response_model=dict)
async def import_candidates_csv(
    election_id: int,
    file: UploadFile = File(...),
    admin_id: str = "admin",
    admin_email: str = "admin@monash.edu",
    db: Session = Depends(get_db)
):
    """Import candidates from CSV file"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    
    if election.is_frozen:
        raise HTTPException(status_code=400, detail="Election is frozen")
    
    content = await file.read()
    csv_reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
    
    added_candidates = []
    for row in csv_reader:
        db_candidate = Candidate(
            election_id=election_id,
            name=row.get('name'),
            faculty=row.get('faculty'),
            manifesto=row.get('manifesto'),
            external_id=row.get('external_id')
        )
        db.add(db_candidate)
        added_candidates.append(db_candidate)
    
    db.commit()
    
    # Log audit action
    log_audit_action(
        db=db,
        action_type=AuditActionType.BULK_IMPORT_CANDIDATES,
        actor_id=admin_id,
        actor_email=admin_email,
        election_id=election_id,
        details={"count": len(added_candidates), "source": "csv", "filename": file.filename}
    )
    
    return {
        "message": f"Successfully imported {len(added_candidates)} candidates from CSV",
        "candidate_ids": [c.id for c in added_candidates]
    }

# Election Template Endpoints
@app.post("/api/templates", response_model=dict)
async def create_election_template(
    template: ElectionTemplateCreate,
    admin_id: str = "admin",
    admin_email: str = "admin@monash.edu",
    db: Session = Depends(get_db)
):
    """Create a reusable election template"""
    db_template = ElectionTemplate(
        name=template.name,
        description=template.description,
        config=template.config,
        created_by=admin_id
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    
    # Log audit action
    log_audit_action(
        db=db,
        action_type=AuditActionType.CREATE_TEMPLATE,
        actor_id=admin_id,
        actor_email=admin_email,
        details={"template_name": template.name, "template_id": db_template.id}
    )
    
    return {"message": "Template created successfully", "template_id": db_template.id}

@app.get("/api/templates", response_model=list)
async def get_templates(db: Session = Depends(get_db)):
    """Get all election templates"""
    templates = db.query(ElectionTemplate).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "created_at": t.created_at.isoformat(),
            "created_by": t.created_by,
            "config": t.config
        }
        for t in templates
    ]

# Voting Endpoints
@app.post("/api/vote", response_model=dict)
async def submit_vote(
    ballot: BallotSubmission,
    db: Session = Depends(get_db)
):
    """Submit a vote with Google authentication"""
    # Check if election exists and is active
    election = db.query(Election).filter(Election.id == ballot.election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    
    if election.is_frozen:
        raise HTTPException(status_code=400, detail="Election is temporarily frozen")
    
    current_time = datetime.now(timezone.utc).replace(tzinfo=None)
    if current_time < election.start_time:
        raise HTTPException(status_code=400, detail="Election has not started yet")
    if current_time > election.end_time:
        raise HTTPException(status_code=400, detail="Election has ended")
    
    # Generate pseudonym from Google ID
    google_info = ballot.google_user_info
    pseudonym = generate_pseudonym(google_info.id, google_info.email)
    
    # Check if voter exists, create if not
    voter = db.query(Voter).filter(Voter.google_id == google_info.id).first()
    if not voter:
        voter = Voter(
            google_id=google_info.id,
            email=google_info.email,
            pseudonym_id=pseudonym,
            faculty=ballot.voter_traits.faculty,
            gender=ballot.voter_traits.gender,
            study_level=ballot.voter_traits.study_level,
            year_level=ballot.voter_traits.year_level
        )
        db.add(voter)
        db.commit()
        db.refresh(voter)
    
    # Check if voter has already voted in this election
    existing_session = db.query(VotingSession).filter(
        VotingSession.voter_id == voter.id,
        VotingSession.election_id == ballot.election_id,
        VotingSession.is_used == True
    ).first()
    
    if existing_session:
        raise HTTPException(status_code=400, detail="You have already voted in this election")
    
    # Create voting session
    session_token = generate_session_token()
    confirmation_code = generate_confirmation_code()
    voting_session = VotingSession(
        session_token=session_token,
        confirmation_code=confirmation_code,
        voter_id=voter.id,
        election_id=ballot.election_id,
        voted_at=current_time,
        is_used=True
    )
    db.add(voting_session)
    db.commit()
    db.refresh(voting_session)
    
    # Generate vote hash for integrity
    vote_hash = generate_vote_hash(ballot.preferences, voter.id, ballot.election_id)
    
    # Store vote
    vote = Vote(
        voting_session_id=voting_session.id,
        preferences=ballot.preferences,
        vote_hash=vote_hash
    )
    db.add(vote)
    db.commit()
    
    # Generate receipt
    receipt_number = generate_receipt_number()
    candidates = db.query(Candidate).filter(Candidate.election_id == ballot.election_id).all()
    receipt_html = generate_vote_receipt_html(
        voter_name=google_info.name or google_info.email,
        election_title=election.title,
        confirmation_code=confirmation_code,
        receipt_number=receipt_number,
        voted_at=current_time,
        candidates=[c.name for c in candidates]
    )
    
    receipt = VoteReceipt(
        voting_session_id=voting_session.id,
        receipt_number=receipt_number,
        receipt_content=receipt_html
    )
    db.add(receipt)
    db.commit()
    
    return {
        "message": "Vote submitted successfully",
        "confirmation_code": confirmation_code,
        "receipt_number": receipt_number,
        "timestamp": current_time.isoformat()
    }

@app.post("/api/verify-vote", response_model=dict)
async def verify_vote(
    verification: VoteVerification,
    db: Session = Depends(get_db)
):
    """Verify that a vote was counted using confirmation code"""
    # Find voting session by confirmation code
    voting_session = db.query(VotingSession).filter(
        VotingSession.confirmation_code == verification.confirmation_code
    ).first()
    
    if not voting_session:
        raise HTTPException(status_code=404, detail="Invalid confirmation code")
    
    # Additional verification with Google ID if provided
    if verification.google_id:
        voter = db.query(Voter).filter(Voter.id == voting_session.voter_id).first()
        if voter.google_id != verification.google_id:
            raise HTTPException(status_code=403, detail="Confirmation code does not match your account")
    
    # Get vote details
    vote = db.query(Vote).filter(Vote.voting_session_id == voting_session.id).first()
    election = db.query(Election).filter(Election.id == voting_session.election_id).first()
    
    # Verify vote integrity
    expected_hash = generate_vote_hash(vote.preferences, voting_session.voter_id, voting_session.election_id)
    integrity_valid = (expected_hash == vote.vote_hash)
    
    return {
        "status": "verified",
        "election_title": election.title,
        "voted_at": voting_session.voted_at.isoformat(),
        "vote_counted": True,
        "integrity_check": "passed" if integrity_valid else "failed",
        "message": "Your vote has been successfully recorded and will be counted in the final tally."
    }

@app.get("/api/receipts/{receipt_number}", response_class=HTMLResponse)
async def get_vote_receipt(
    receipt_number: str,
    db: Session = Depends(get_db)
):
    """Retrieve vote receipt by receipt number"""
    receipt = db.query(VoteReceipt).filter(
        VoteReceipt.receipt_number == receipt_number
    ).first()
    
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    return HTMLResponse(content=receipt.receipt_content)

# Results and Analytics
@app.get("/api/elections/{election_id}/results", response_model=ElectionResults)
async def get_election_results(
    election_id: int,
    db: Session = Depends(get_db)
):
    """Get election results and analytics"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    
    # Get all votes for this election
    votes = db.query(Vote).join(VotingSession).filter(
        VotingSession.election_id == election_id
    ).all()
    
    # Get voter demographics
    voters = db.query(Voter).join(VotingSession).filter(
        VotingSession.election_id == election_id,
        VotingSession.is_used == True
    ).all()
    
    # Calculate turnout by demographics
    turnout_by_faculty = defaultdict(int)
    turnout_by_gender = defaultdict(int)
    turnout_by_study_level = defaultdict(int)
    
    for voter in voters:
        turnout_by_faculty[voter.faculty] += 1
        turnout_by_gender[voter.gender] += 1
        turnout_by_study_level[voter.study_level] += 1
    
    # Calculate first preference counts
    candidates = db.query(Candidate).filter(Candidate.election_id == election_id).all()
    candidate_names = {c.id: c.name for c in candidates}
    
    first_pref_counts = defaultdict(int)
    for vote in votes:
        preferences = vote.preferences
        # Find candidate with preference 1
        for cand_id, pref in preferences.items():
            if pref == 1:
                first_pref_counts[candidate_names.get(int(cand_id), "Unknown")] += 1
                break
    
    # Determine status
    current_time = datetime.utcnow()
    if election.is_frozen:
        status = "frozen"
    elif current_time < election.start_time:
        status = "scheduled"
    elif current_time > election.end_time:
        status = "closed"
    else:
        status = "active"
    
    return ElectionResults(
        election_id=election_id,
        title=election.title,
        total_votes=len(votes),
        turnout_by_faculty=dict(turnout_by_faculty),
        turnout_by_gender=dict(turnout_by_gender),
        turnout_by_study_level=dict(turnout_by_study_level),
        vote_counts=dict(first_pref_counts),
        status=status
    )

# Audit Trail Endpoints
@app.get("/api/audit-logs", response_model=list)
async def get_audit_logs(
    election_id: Optional[int] = None,
    actor_id: Optional[str] = None,
    limit: int = 100,
    admin_id: str = "admin",
    admin_email: str = "admin@monash.edu",
    db: Session = Depends(get_db)
):
    """Get audit logs with optional filtering"""
    query = db.query(AuditLog)
    
    if election_id:
        query = query.filter(AuditLog.election_id == election_id)
    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)
    
    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    # Log this audit log access
    log_audit_action(
        db=db,
        action_type=AuditActionType.VIEW_AUDIT_LOG,
        actor_id=admin_id,
        actor_email=admin_email,
        details={"filters": {"election_id": election_id, "actor_id": actor_id}}
    )
    
    return [
        {
            "id": log.id,
            "action_type": log.action_type,
            "actor_id": log.actor_id,
            "actor_email": log.actor_email,
            "election_id": log.election_id,
            "details": log.details,
            "timestamp": log.timestamp.isoformat(),
            "ip_address": log.ip_address
        }
        for log in logs
    ]

# Additional Admin Endpoints
@app.post("/api/elections/{election_id}/freeze", response_model=dict)
async def freeze_election(
    election_id: int,
    admin_id: str = "admin",
    admin_email: str = "admin@monash.edu",
    db: Session = Depends(get_db)
):
    """Freeze an election (temporarily prevent voting)"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    
    election.is_frozen = True
    db.commit()
    
    log_audit_action(
        db=db,
        action_type=AuditActionType.FREEZE_ELECTION,
        actor_id=admin_id,
        actor_email=admin_email,
        election_id=election_id,
        details={"reason": "Admin action"}
    )
    
    return {"message": "Election frozen successfully"}

@app.post("/api/elections/{election_id}/unfreeze", response_model=dict)
async def unfreeze_election(
    election_id: int,
    admin_id: str = "admin",
    admin_email: str = "admin@monash.edu",
    db: Session = Depends(get_db)
):
    """Unfreeze an election (resume voting)"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    
    election.is_frozen = False
    db.commit()
    
    log_audit_action(
        db=db,
        action_type=AuditActionType.UNFREEZE_ELECTION,
        actor_id=admin_id,
        actor_email=admin_email,
        election_id=election_id,
        details={"reason": "Admin action"}
    )
    
    return {"message": "Election unfrozen successfully"}

# Get all elections
@app.get("/api/elections", response_model=list)
async def get_elections(db: Session = Depends(get_db)):
    """Get all elections"""
    elections = db.query(Election).all()
    return [
        {
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "start_time": e.start_time.isoformat(),
            "end_time": e.end_time.isoformat(),
            "is_frozen": e.is_frozen,
            "status": "frozen" if e.is_frozen else ("active" if datetime.utcnow() >= e.start_time and datetime.utcnow() <= e.end_time else "inactive")
        }
        for e in elections
    ]

@app.get("/api/elections/{election_id}/candidates")
async def get_candidates(
    election_id: int,
    db: Session = Depends(get_db)
):
    """Get all candidates for an election"""
    candidates = db.query(Candidate).filter(Candidate.election_id == election_id).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "faculty": c.faculty,
            "manifesto": c.manifesto,
            "external_id": c.external_id
        }
        for c in candidates
    ]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)