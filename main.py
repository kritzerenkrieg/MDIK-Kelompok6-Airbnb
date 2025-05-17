# main.py
from fastapi import FastAPI, Depends, Query, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, Text, Float, Date, Numeric
from sqlalchemy.future import select
from pydantic import BaseModel, validator
from typing import List, Optional
import datetime

# Database URL: root user, no password, database 'airbnb'
DATABASE_URL = "mysql+aiomysql://root:@localhost/airbnb"

# Async engine & session
engine = create_async_engine(
    DATABASE_URL, 
    echo=True,
    pool_size=50,
    max_overflow=100,
    pool_recycle=3600
    )
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()

# SQLAlchemy model matching provided MySQL schema
class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    host_id = Column(Integer, nullable=False)
    host_name = Column(Text, nullable=False)
    neighbourhood_group = Column(Text)
    neighbourhood = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    room_type = Column(Text)
    price = Column(Numeric)
    minimum_nights = Column(Integer)
    number_of_reviews = Column(Integer)
    last_review = Column(Date)
    reviews_per_month = Column(Float)
    calculated_host_listings_count = Column(Integer)
    availability_365 = Column(Integer)
    number_of_reviews_ltm = Column(Integer)
    license = Column(Text)

# Pydantic schema with custom parsing for last_review
class ListingSchema(BaseModel):
    id: int
    name: str
    host_id: int
    host_name: str
    neighbourhood_group: Optional[str]
    neighbourhood: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    room_type: Optional[str]
    price: Optional[float]
    minimum_nights: Optional[int]
    number_of_reviews: Optional[int]
    last_review: Optional[datetime.date]
    reviews_per_month: Optional[float]
    calculated_host_listings_count: Optional[int]
    availability_365: Optional[int]
    number_of_reviews_ltm: Optional[int]
    license: Optional[str]

    @validator('last_review', pre=True)
    def parse_last_review(cls, v):
        if not v or str(v) == '0000-00-00':
            return None
        if isinstance(v, datetime.date):
            return v
        s = str(v)
        for fmt in ('%Y-%m-%d', '%m/%d/%Y'):
            try:
                return datetime.datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        raise ValueError(f'Invalid date format: {s}')

    class Config:
        orm_mode = True

# FastAPI application
app = FastAPI()

# Exception handler for validation errors -> 400 Bad Request
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors(), "body": exc.body},
    )

# Exception handler for unexpected errors -> 500 Internal Server Error
@app.exception_handler(Exception)
async def internal_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )

# Create tables on startup
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Dependency: DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# GET listings with pagination, filtering, sorting, and search
@app.get("/listings", response_model=List[ListingSchema])
async def read_listings(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    neighbourhood: Optional[str] = Query(None),
    price_lte: Optional[float] = Query(None),
    search: Optional[str] = Query(None, description="Search in name or neighbourhood"),
    sort_by: str = Query("price"),
    order: str = Query("asc"),
    db: AsyncSession = Depends(get_db),
):
    skip = (page - 1) * limit
    stmt = select(Listing)
    if neighbourhood:
        stmt = stmt.where(Listing.neighbourhood == neighbourhood)
    if price_lte is not None:
        stmt = stmt.where(Listing.price <= price_lte)
    if search:
        like_pattern = f"%{search}%"
        stmt = stmt.where(
            Listing.name.ilike(like_pattern) | Listing.neighbourhood.ilike(like_pattern)
        )
    col = getattr(Listing, sort_by, Listing.price)
    stmt = stmt.order_by(col.desc() if order.lower() == "desc" else col.asc())
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

# POST new listing
@app.post("/listings", response_model=ListingSchema, status_code=201)
async def create_listing(
    listing: ListingSchema,
    db: AsyncSession = Depends(get_db),
):
    try:
        data = listing.dict(exclude={"id"})
        new = Listing(**data)
        db.add(new)
        await db.commit()
        await db.refresh(new)
        return new
    except Exception:
        raise

# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}

# To run: uvicorn main:app --reload
