#!/usr/bin/env python3
"""
Database Initialization Script for Monash Voting System
Run this script to initialize or reset the database with proper schema
"""

import os
import sys
from datetime import datetime, timedelta, timezone

def init_database():
    """Initialize or reset the database"""
    
    print("="*60)
    print("MONASH VOTING SYSTEM - DATABASE INITIALIZATION")
    print("="*60)
    
    # Check if database exists
    if os.path.exists("voting_system.db"):
        print("\n⚠️  WARNING: Existing database found!")
        response = input("Do you want to delete it and create a fresh one? (yes/no): ").lower()
        
        if response == 'yes':
            try:
                os.remove("voting_system.db")
                print("✅ Old database deleted successfully.")
            except Exception as e:
                print(f"❌ Error deleting database: {e}")
                return False
        else:
            print("ℹ️  Keeping existing database. Exiting...")
            return False
    
    print("\n📊 Creating new database with latest schema...")
    
    # Import backend to create tables
    try:
        # Import all necessary modules from backend
        from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, JSON, Float, Text
        from sqlalchemy.orm import declarative_base, sessionmaker, relationship
        from datetime import datetime
        
        # Create engine and base
        SQLALCHEMY_DATABASE_URL = "sqlite:///./voting_system.db"
        engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base = declarative_base()
        
        # Define all models with complete schema
        class Election(Base):
            __tablename__ = "elections"
            
            id = Column(Integer, primary_key=True, index=True)
            title = Column(String, nullable=False)
            description = Column(String)
            start_time = Column(DateTime, nullable=False)
            end_time = Column(DateTime, nullable=False)
            created_at = Column(DateTime, default=datetime.utcnow)
            is_active = Column(Boolean, default=True)
            is_frozen = Column(Boolean, default=False)  # Important: New field
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
            config = Column(JSON)
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
            external_id = Column(String)
            
            election = relationship("Election", back_populates="candidates")

        class Voter(Base):
            __tablename__ = "voters"
            
            id = Column(Integer, primary_key=True, index=True)
            google_id = Column(String, unique=True, index=True)
            email = Column(String, index=True)
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
            confirmation_code = Column(String, unique=True, index=True)
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
            preferences = Column(JSON)
            submitted_at = Column(DateTime, default=datetime.utcnow)
            vote_hash = Column(String)
            
            voting_session = relationship("VotingSession", back_populates="votes")

        class VoteReceipt(Base):
            __tablename__ = "vote_receipts"
            
            id = Column(Integer, primary_key=True, index=True)
            voting_session_id = Column(Integer, ForeignKey("voting_sessions.id"))
            receipt_number = Column(String, unique=True, index=True)
            receipt_content = Column(Text)
            generated_at = Column(DateTime, default=datetime.utcnow)
            
            voting_session = relationship("VotingSession", back_populates="vote_receipts")

        class AuditLog(Base):
            __tablename__ = "audit_logs"
            
            id = Column(Integer, primary_key=True, index=True)
            action_type = Column(String, nullable=False)
            actor_id = Column(String, nullable=False)
            actor_email = Column(String)
            election_id = Column(Integer, ForeignKey("elections.id"), nullable=True)
            details = Column(JSON)
            timestamp = Column(DateTime, default=datetime.utcnow)
            ip_address = Column(String)
            
            election = relationship("Election", back_populates="audit_logs")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("✅ All tables created successfully!")
        
        # Optional: Create sample data
        response = input("\nDo you want to create sample test data? (yes/no): ").lower()
        
        if response == 'yes':
            db = SessionLocal()
            try:
                # Create a sample election
                utc_now = datetime.now(timezone.utc)
                sample_election = Election(
                    title="Sample Student Council Election",
                    description="This is a test election for demonstration",
                    start_time=utc_now - timedelta(hours=1),
                    end_time=utc_now + timedelta(days=7),
                    is_active=True,
                    is_frozen=False
                )
                db.add(sample_election)
                db.commit()
                db.refresh(sample_election)
                
                # Add sample candidates
                candidates = [
                    Candidate(election_id=sample_election.id, name="Alice Chen", faculty="Engineering", 
                             manifesto="Innovation and progress for all students"),
                    Candidate(election_id=sample_election.id, name="Bob Smith", faculty="Business", 
                             manifesto="Financial responsibility and transparency"),
                    Candidate(election_id=sample_election.id, name="Carol Wang", faculty="Arts", 
                             manifesto="Creative expression and student wellness"),
                ]
                
                for candidate in candidates:
                    db.add(candidate)
                db.commit()
                
                # Create a sample template
                template = ElectionTemplate(
                    name="Standard Election Template",
                    description="Default template for student elections",
                    config={
                        "duration_days": 7,
                        "voting_method": "IRV",
                        "require_manifesto": True,
                        "max_candidates": 10
                    },
                    created_by="admin"
                )
                db.add(template)
                db.commit()
                
                print("✅ Sample data created successfully!")
                print(f"   - 1 active election: '{sample_election.title}'")
                print(f"   - 3 candidates added")
                print(f"   - 1 election template created")
                
            except Exception as e:
                print(f"❌ Error creating sample data: {e}")
                db.rollback()
            finally:
                db.close()
        
        print("\n" + "="*60)
        print("✅ DATABASE INITIALIZATION COMPLETE!")
        print("="*60)
        print("\nYou can now run:")
        print("  1. python backend.py      - Start the backend API")
        print("  2. python integrated_login.py  - Start the login interface")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Make sure you have all required packages installed:")
        print("  pip install sqlalchemy fastapi uvicorn pydantic")
        return False
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False

if __name__ == "__main__":
    success = init_database()
    if not success:
        sys.exit(1)