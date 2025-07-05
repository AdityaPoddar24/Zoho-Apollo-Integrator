from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy import (
    BigInteger, String, Integer, Boolean, DateTime, JSON, ForeignKey, Text
)
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    apollo_org_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    name:            Mapped[str] = mapped_column(String(255))
    domain_resolved: Mapped[str | None] = mapped_column(String(255))
    domain_entered:  Mapped[str | None] = mapped_column(String(255))
    industry:        Mapped[str | None] = mapped_column(String(255))
    employee_count:  Mapped[int | None]
    revenue:         Mapped[int | None]
    location_city:   Mapped[str | None] = mapped_column(String(128))
    location_country:Mapped[str | None] = mapped_column(String(64))
    is_enriched:     Mapped[bool] = mapped_column(Boolean, default=False)
    enriched_at:     Mapped[datetime | None]
    created_at:      Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at:      Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    details = relationship("OrganizationDetails", uselist=False, back_populates="company")
    people   = relationship("Person", secondary="company_people")

class OrganizationDetails(Base):
    __tablename__ = "organization_details"
    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True
    )
    company = relationship("Company", back_populates="details")
    website_url: Mapped[str | None] = mapped_column(String(255))
    blog_url:    Mapped[str | None] = mapped_column(String(255))
    angellist_url: Mapped[str | None] = mapped_column(String(255))
    linkedin_url:  Mapped[str | None] = mapped_column(String(255))
    twitter_url:   Mapped[str | None] = mapped_column(String(255))
    facebook_url:  Mapped[str | None] = mapped_column(String(255))
    primary_phone: Mapped[dict | None] = mapped_column(JSON)
    languages:     Mapped[list | None] = mapped_column(JSON)
    alexa_ranking: Mapped[int | None]
    phone:         Mapped[str | None] = mapped_column(String(64))
    linkedin_uid:  Mapped[str | None] = mapped_column(String(40))
    founded_year:  Mapped[int | None]
    publicly_traded_symbol:  Mapped[str | None] = mapped_column(String(20))
    publicly_traded_exchange:Mapped[str | None] = mapped_column(String(20))
    logo_url:      Mapped[str | None] = mapped_column(String(255))
    crunchbase_url:Mapped[str | None] = mapped_column(String(255))
    primary_domain:Mapped[str | None] = mapped_column(String(255))
    keywords:      Mapped[list | None] = mapped_column(JSON)
    estimated_num_employees: Mapped[int | None]
    industries:    Mapped[list | None] = mapped_column(JSON)
    secondary_industries: Mapped[list | None] = mapped_column(JSON)
    snippets_loaded: Mapped[bool | None]
    industry_tag_id:     Mapped[str | None] = mapped_column(String(40))
    industry_tag_hash:   Mapped[dict | None] = mapped_column(JSON)
    retail_location_count: Mapped[int | None]
    raw_address:    Mapped[str | None] = mapped_column(String(512))
    street_address: Mapped[str | None] = mapped_column(String(255))
    city:           Mapped[str | None] = mapped_column(String(128))
    state:          Mapped[str | None] = mapped_column(String(128))
    postal_code:    Mapped[str | None] = mapped_column(String(20))
    country:        Mapped[str | None] = mapped_column(String(128))
    owned_by_organization_id: Mapped[str | None] = mapped_column(String(40))
    seo_description:   Mapped[str | None] = mapped_column(Text)
    short_description: Mapped[str | None] = mapped_column(Text)
    suborganizations:  Mapped[list | None] = mapped_column(JSON)
    num_suborganizations: Mapped[int | None]
    annual_revenue_printed: Mapped[str | None] = mapped_column(String(50))
    annual_revenue:    Mapped[int | None]
    total_funding:     Mapped[int | None]
    total_funding_printed: Mapped[str | None] = mapped_column(String(50))
    latest_funding_round_date: Mapped[datetime | None]
    latest_funding_stage: Mapped[str | None] = mapped_column(String(50))
    funding_events:   Mapped[list | None] = mapped_column(JSON)
    technology_names: Mapped[list | None] = mapped_column(JSON)
    org_chart_root_people_ids: Mapped[list | None] = mapped_column(JSON)
    org_chart_sector: Mapped[str | None] = mapped_column(String(255))
    org_chart_removed:            Mapped[bool | None]
    org_chart_show_department_filter: Mapped[bool | None]
    account_id:      Mapped[str | None] = mapped_column(String(40))
    departmental_head_count: Mapped[dict | None] = mapped_column(JSON)
    created_at:      Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at:      Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

class Person(Base):
    __tablename__ = "people"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    apollo_person_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    first_name:       Mapped[str] = mapped_column(String(128))
    last_name:        Mapped[str] = mapped_column(String(128))
    title:            Mapped[str | None] = mapped_column(String(255))
    seniority:        Mapped[str | None] = mapped_column(String(64))
    email:            Mapped[str | None] = mapped_column(String(255))
    phone:            Mapped[str | None] = mapped_column(String(64))
    linkedin_url:     Mapped[str | None] = mapped_column(String(255))
    location_city:    Mapped[str | None] = mapped_column(String(128))
    location_country: Mapped[str | None] = mapped_column(String(64))
    is_enriched:      Mapped[bool] = mapped_column(Boolean, default=False)
    enriched_at:      Mapped[datetime | None]
    created_at:       Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at:       Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    details = relationship("PersonDetails", uselist=False, back_populates="person")

class PersonDetails(Base):
    __tablename__ = "person_details"
    person_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("people.id", ondelete="CASCADE"), primary_key=True
    )
    person = relationship("Person", back_populates="details")

    photo_url:         Mapped[str | None] = mapped_column(String(255))
    linkedin_url_full: Mapped[str | None] = mapped_column(String(255))
    headline:          Mapped[str | None] = mapped_column(String(255))
    email_status:      Mapped[str | None] = mapped_column(String(32))
    twitter_url:       Mapped[str | None] = mapped_column(String(255))
    github_url:        Mapped[str | None] = mapped_column(String(255))
    facebook_url:      Mapped[str | None] = mapped_column(String(255))
    extrapolated_email_confidence: Mapped[str | None] = mapped_column(String(32))
    contact_id:        Mapped[str | None] = mapped_column(String(40))
    contact_blob:      Mapped[dict | None] = mapped_column(JSON)
    revealed_for_current_team: Mapped[bool | None]
    is_likely_to_engage:      Mapped[bool | None]
    intent_strength:          Mapped[str | None] = mapped_column(String(64))
    show_intent:              Mapped[bool | None]
    departments:              Mapped[list | None] = mapped_column(JSON)
    subdepartments:           Mapped[list | None] = mapped_column(JSON)
    functions:                Mapped[list | None] = mapped_column(JSON)
    contact_emails:           Mapped[list | None] = mapped_column(JSON)
    phone_numbers:            Mapped[list | None] = mapped_column(JSON)
    typed_custom_fields:      Mapped[dict | None] = mapped_column(JSON)
    country:                  Mapped[str | None] = mapped_column(String(128))
    state:                    Mapped[str | None] = mapped_column(String(128))
    city:                     Mapped[str | None] = mapped_column(String(128))
    time_zone:                Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

class CompanyPeople(Base):
    __tablename__ = "company_people"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("companies.id", ondelete="CASCADE")
    )
    person_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("people.id", ondelete="CASCADE")
    )
