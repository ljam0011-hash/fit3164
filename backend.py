from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional, Dict
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func
import secrets
import hashlib
import json
from collections import defaultdict
import uvicorn

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./voting_system.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# FastAPI app
app = FastAPI(title="Monash Club Electronic Voting System", version="1.0.0")

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
    
    candidates = relationship("Candidate", back_populates="election")
    voting_sessions = relationship("VotingSession", back_populates="election")

class Candidate(Base):
    __tablename__ = "candidates"
    
    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(Integer, ForeignKey("elections.id"))
    name = Column(String, nullable=False)
    faculty = Column(String)
    manifesto = Column(String)
    
    election = relationship("Election", back_populates="candidates")

class Voter(Base):
    __tablename__ = "voters"
    
    id = Column(Integer, primary_key=True, index=True)
    pseudonym_id = Column(String, unique=True, index=True)
    faculty = Column(String)
    gender = Column(String)
    study_level = Column(String)
    year_level = Column(Integer)
    
    voting_sessions = relationship("VotingSession", back_populates="voter")

class VotingSession(Base):
    __tablename__ = "voting_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(String, unique=True, index=True)
    voter_id = Column(Integer, ForeignKey("voters.id"))
    election_id = Column(Integer, ForeignKey("elections.id"))
    voted_at = Column(DateTime)
    is_used = Column(Boolean, default=False)
    
    voter = relationship("Voter", back_populates="voting_sessions")
    election = relationship("Election", back_populates="voting_sessions")
    votes = relationship("Vote", back_populates="voting_session")

class Vote(Base):
    __tablename__ = "votes"
    
    id = Column(Integer, primary_key=True, index=True)
    voting_session_id = Column(Integer, ForeignKey("voting_sessions.id"))
    preferences = Column(JSON)  # Stores ranked preferences as JSON
    submitted_at = Column(DateTime, default=datetime.utcnow)
    
    voting_session = relationship("VotingSession", back_populates="votes")

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic models
class ElectionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime

class CandidateCreate(BaseModel):
    name: str
    faculty: Optional[str] = None
    manifesto: Optional[str] = None

class VoterTraits(BaseModel):
    faculty: str
    gender: str
    study_level: str
    year_level: int

class BallotSubmission(BaseModel):
    email: EmailStr = Field(..., description="Must be a @monash.edu email")
    election_id: int
    preferences: Dict[int, int]  # candidate_id: preference_rank
    voter_traits: VoterTraits
    
    @validator('email')
    def validate_monash_email(cls, v):
        if not v.endswith('@monash.edu'):
            raise ValueError('Must be a valid @monash.edu email address')
        return v
    
    @validator('preferences')
    def validate_preferences(cls, v):
        ranks = list(v.values())
        if sorted(ranks) != list(range(1, len(ranks) + 1)):
            raise ValueError('Preferences must be a complete ranking starting from 1')
        return v

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

def generate_pseudonym(email: str):
    """Generate a pseudonymous ID from email"""
    return hashlib.sha256(email.encode()).hexdigest()[:16]

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
    return {"message": "Monash Club Electronic Voting System API", "version": "1.0.0"}

@app.post("/api/elections", response_model=dict)
async def create_election(
    election: ElectionCreate,
    db: Session = Depends(get_db)
):
    """Create a new election (Admin only - auth not implemented for demo)"""
    db_election = Election(**election.dict())
    db.add(db_election)
    db.commit()
    db.refresh(db_election)
    return {"message": "Election created successfully", "election_id": db_election.id}

@app.post("/api/elections/{election_id}/candidates", response_model=dict)
async def add_candidate(
    election_id: int,
    candidate: CandidateCreate,
    db: Session = Depends(get_db)
):
    """Add a candidate to an election"""
    # Check if election exists
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    
    db_candidate = Candidate(election_id=election_id, **candidate.dict())
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    return {"message": "Candidate added successfully", "candidate_id": db_candidate.id}

@app.post("/api/vote", response_model=dict)
async def submit_vote(
    ballot: BallotSubmission,
    db: Session = Depends(get_db)
):
    """Submit a vote"""
    # Check if election exists and is active
    election = db.query(Election).filter(Election.id == ballot.election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    
    # Use timezone-aware datetime
    current_time = datetime.now(timezone.utc).replace(tzinfo=None)
    if current_time < election.start_time:
        raise HTTPException(status_code=400, detail="Election has not started yet")
    if current_time > election.end_time:
        raise HTTPException(status_code=400, detail="Election has ended")
    
    # Generate pseudonym from email
    pseudonym = generate_pseudonym(ballot.email)
    
    # Check if voter exists, create if not
    voter = db.query(Voter).filter(Voter.pseudonym_id == pseudonym).first()
    if not voter:
        voter = Voter(
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
    voting_session = VotingSession(
        session_token=session_token,
        voter_id=voter.id,
        election_id=ballot.election_id,
        voted_at=current_time,
        is_used=True
    )
    db.add(voting_session)
    db.commit()
    db.refresh(voting_session)
    
    # Store vote
    vote = Vote(
        voting_session_id=voting_session.id,
        preferences=ballot.preferences
    )
    db.add(vote)
    db.commit()
    
    return {
        "message": "Vote submitted successfully",
        "confirmation_code": session_token[:8],
        "timestamp": current_time.isoformat()
    }

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
            "status": "active" if datetime.utcnow() >= e.start_time and datetime.utcnow() <= e.end_time else "inactive"
        }
        for e in elections
    ]

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
    if current_time < election.start_time:
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
            "manifesto": c.manifesto
        }
        for c in candidates
    ]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)