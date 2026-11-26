"""SQLAlchemy models for the ISIR Watcher application."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from src.database import Base


class WatchedEntity(Base):
    """Model for entities being watched on the website."""
    
    __tablename__ = "watched_entities"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Entity information
    name = Column(String(255), nullable=False)
    isir_id = Column(String(255), nullable=False, unique=True, index=True)
    
    # Tracking information
    last_checked = Column(DateTime, nullable=True)
    last_modified = Column(DateTime, nullable=True)
    
    # Silent mode - if True, changes won't be included in changelog
    silent = Column(Boolean, nullable=False, default=False)
    
    # Number of consecutive checks where the ISIR link was invalid (reset on success).
    # Used to suppress transient INVALID_LINK errors from the changelog.
    consecutive_failures = Column(Integer, nullable=False, default=0)
    
    # Relationships to document types
    before_bankruptcy_docs = relationship("BeforeBankruptcyDocument", back_populates="watched_entity", cascade="all, delete-orphan")
    after_bankruptcy_docs = relationship("AfterBankruptcyDocument", back_populates="watched_entity", cascade="all, delete-orphan")
    other_docs = relationship("OtherDocument", back_populates="watched_entity", cascade="all, delete-orphan")
    application_docs = relationship("ApplicationDocument", back_populates="watched_entity", cascade="all, delete-orphan")
    dispute_docs = relationship("DisputeDocument", back_populates="watched_entity", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<WatchedEntity(id={self.id}, name='{self.name}', isir_id='{self.isir_id}')>"


class DocumentFieldsMixin:
    """Mixin class containing common fields for all document types."""
    
    # Primary key - auto-incrementing integer
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign key to watched entity
    watched_entity_id = Column(Integer, ForeignKey("watched_entities.id"), nullable=False, index=True)
    
    # ISIR document ID (unique per entity, not globally)
    isir_document_id = Column(String(10), nullable=False)
    
    # Document information
    document_type = Column(String(50), nullable=True)  # e.g., "I_63", "I_126", etc.
    publish_date = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    document_id = Column(String(255), nullable=True)  # Extracted from PDF link
    side_document_id = Column(String(255), nullable=True)  # Extracted from PDF link
    legally_binding_date = Column(DateTime, nullable=True)
    senat_number = Column(String(255), nullable=True)
    
    # Track if document was deleted from ISIR
    is_deleted = Column(Integer, nullable=False, default=0)  # Using Integer for SQLite boolean compatibility
    
    # HTTP status codes from download attempts
    download = Column(Integer, nullable=True)  # HTTP status code for main document
    side_download = Column(Integer, nullable=True)  # HTTP status code for side document
    
    def get_html_document_id(self):
        """
        Get HTML-formatted document ID with section letter and non-breaking characters.
        
        Returns:
            str: HTML-formatted document ID (e.g., "A&nbsp;&#8209;&nbsp;1.")
        """
        # Get section letter from the class (must be defined in subclasses)
        section_letter = getattr(self.__class__, 'SECTION_LETTER', '')
        
        # Format ID with section letter (only for A/B/D, C/P already has it)
        if section_letter in ['A', 'B', 'D']:
            display_id = f"{section_letter} - {self.isir_document_id}"
        else:
            display_id = self.isir_document_id
        
        # Replace all spaces with non-breaking spaces and dash with non-breaking hyphen
        display_id = display_id.replace(' ', '&nbsp;').replace('-', '&#8209;')
        
        return display_id


class BeforeBankruptcyDocument(DocumentFieldsMixin, Base):
    """Documents from before bankruptcy."""
    
    __tablename__ = "before_bankruptcy_documents"
    SECTION_LETTER = 'A'
    
    # Relationships
    watched_entity = relationship("WatchedEntity", back_populates="before_bankruptcy_docs")
    
    def __repr__(self):
        return f"<BeforeBankruptcyDocument(id={self.id}, isir_document_id='{self.isir_document_id}')>"


class AfterBankruptcyDocument(DocumentFieldsMixin, Base):
    """Documents from after bankruptcy."""
    
    __tablename__ = "after_bankruptcy_documents"
    SECTION_LETTER = 'B'
    
    # Relationships
    watched_entity = relationship("WatchedEntity", back_populates="after_bankruptcy_docs")
    
    def __repr__(self):
        return f"<AfterBankruptcyDocument(id={self.id}, isir_document_id='{self.isir_document_id}')>"


class OtherDocument(DocumentFieldsMixin, Base):
    """Other documents not categorized as before or after bankruptcy."""
    
    __tablename__ = "other_documents"
    SECTION_LETTER = 'D'
    
    # Relationships
    watched_entity = relationship("WatchedEntity", back_populates="other_docs")
    
    def __repr__(self):
        return f"<OtherDocument(id={self.id}, isir_document_id='{self.isir_document_id}')>"


class ApplicationDocument(DocumentFieldsMixin, Base):
    """Application document with additional creditor field."""
    
    __tablename__ = "application_documents"
    SECTION_LETTER = 'P'
    
    # Additional fields specific to applications
    creditor = Column(String(255), nullable=True)
    
    # Relationships
    watched_entity = relationship("WatchedEntity", back_populates="application_docs")
    
    def __repr__(self):
        return f"<ApplicationDocument(id={self.id}, isir_document_id='{self.isir_document_id}', creditor='{self.creditor}')>"


class DisputeDocument(DocumentFieldsMixin, Base):
    """Dispute document with additional dispute number field."""
    
    __tablename__ = "dispute_documents"
    SECTION_LETTER = 'C'
    
    # Additional fields specific to disputes
    dispute_number = Column(String(255), nullable=True)
    
    # Relationships
    watched_entity = relationship("WatchedEntity", back_populates="dispute_docs")
    
    def __repr__(self):
        return f"<DisputeDocument(id={self.id}, isir_document_id='{self.isir_document_id}', dispute_number='{self.dispute_number}')>"
