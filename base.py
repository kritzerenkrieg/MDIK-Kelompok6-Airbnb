## Database Configuration (database.py)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "mysql+aiomysql://root@localhost:3306/airbnb"

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

## Models (models.py)
from sqlalchemy import Column, Integer, String, Float, Date
from sqlalchemy.orm import declarative_base  # ✅ recommended for SQLAlchemy 2.x

Base = declarative_base()

class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    host_id = Column(Integer, nullable=False)
    host_name = Column(String(255), nullable=False)
    neighbourhood_group = Column(String(255))
    neighbourhood = Column(String(255))
    latitude = Column(Float)
    longitude = Column(Float)
    room_type = Column(String(100))
    price = Column(Integer)
    minimum_nights = Column(Integer)
    number_of_reviews = Column(Integer)
    last_review = Column(Date)
    reviews_per_month = Column(Float)
    calculated_host_listings_count = Column(Integer)
    availability_365 = Column(Integer)
    number_of_reviews_ltm = Column(Integer)
    license = Column(String(255))


## Schemas (schemas.py)
from pydantic import BaseModel
from datetime import date
from typing import Optional

class ListingBase(BaseModel):
    name: str
    host_id: int
    host_name: str
    neighbourhood_group: Optional[str]
    neighbourhood: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    room_type: Optional[str]
    price: Optional[int]
    minimum_nights: Optional[int]
    number_of_reviews: Optional[int]
    last_review: Optional[date]
    reviews_per_month: Optional[float]
    calculated_host_listings_count: Optional[int]
    availability_365: Optional[int]
    number_of_reviews_ltm: Optional[int]
    license: Optional[str]

class ListingCreate(ListingBase):
    pass

class Listing(ListingBase):
    id: int

    class Config:
        from_attributes = True


## CRUD Operations (crud.py)
from sqlalchemy.future import select
from sqlalchemy import update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

async def get_listings(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    neighbourhood: Optional[str] = None,
    price_lte: Optional[int] = None,
    sort_by: str = "price",
    order: str = "asc",
) -> List[Listing]:
    query = select(Listing)
    if neighbourhood:
        query = query.filter(Listing.neighbourhood == neighbourhood)
    if price_lte is not None:
        query = query.filter(Listing.price <= price_lte)
    if order.lower() == "desc":
        order_expr = getattr(Listing, sort_by).desc()
    else:
        order_expr = getattr(Listing, sort_by).asc()
    query = query.order_by(order_expr).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def create_listing(db: AsyncSession, listing: ListingCreate) -> Listing:
    db_listing = Listing(**listing.dict())
    db.add(db_listing)
    await db.commit()
    await db.refresh(db_listing)
    return db_listing


## Main Application (main.py)
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

app = FastAPI(title="Airbnb Listings API")

# Create tables
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Dependency
async def get_db():
    async for session in get_db():
        yield session

@app.get("/listings", response_model=List[Listing])
async def read_listings(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    neighbourhood: Optional[str] = Query(None),
    price_lte: Optional[int] = Query(None, alias="price_lte"),
    sort_by: str = Query("price"),
    order: str = Query("asc"),
    db: AsyncSession = Depends(get_db),
):
    skip = (page - 1) * limit
    return await get_listings(
        db=db,
        skip=skip,
        limit=limit,
        neighbourhood=neighbourhood,
        price_lte=price_lte,
        sort_by=sort_by,
        order=order,
    )

@app.post("/listings", response_model=Listing, status_code=201)
async def create_new_listing(
    listing: ListingCreate,
    db: AsyncSession = Depends(get_db),
):
    return await create_listing(db, listing)

@app.get("/list")
async def get_listings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Listing))
    listings = result.scalars().all()
    return listings

@app.get("/health")
def health_check():
    return {"status": "OK"}

# To run: uvicorn main:app --reload
