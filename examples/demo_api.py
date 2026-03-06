#!/usr/bin/env python3
"""
Demo API - Example FastAPI application for testing ai-testing-agent.

Run analyze-code against this file:
    python cli.py analyze-code examples/demo_api.py --output ./tests

No real server needed — this file is just used for code analysis.
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Demo API")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# --- Models ---

class UserCreate(BaseModel):
    email: str
    password: str
    name: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ProductCreate(BaseModel):
    name: str
    price: float
    category: str
    stock: int


# --- Auth ---

@app.post("/api/auth/login")
async def login(body: LoginRequest):
    """Authenticate user and return token."""
    return {"token": "jwt-token-here", "user_id": 1}


@app.post("/api/auth/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    """Invalidate the current session token."""
    return {"message": "Logged out"}


# --- Users ---

@app.get("/api/users")
async def list_users(
    page: int = 1,
    limit: int = 20,
    token: str = Depends(oauth2_scheme)
):
    """List all users with pagination."""
    return {"users": [], "total": 0, "page": page}


@app.post("/api/users")
async def create_user(body: UserCreate, token: str = Depends(oauth2_scheme)):
    """Create a new user account."""
    return {"id": 1, "email": body.email, "name": body.name}


@app.get("/api/users/{user_id}")
async def get_user(user_id: int, token: str = Depends(oauth2_scheme)):
    """Get a specific user by ID."""
    return {"id": user_id, "email": "user@example.com", "name": "Test User"}


@app.put("/api/users/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdate,
    token: str = Depends(oauth2_scheme)
):
    """Update an existing user."""
    return {"id": user_id, "updated": True}


@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, token: str = Depends(oauth2_scheme)):
    """Delete a user account."""
    return {"deleted": True}


# --- Products ---

@app.get("/api/products")
async def list_products(
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    page: int = 1
):
    """List products with optional filters. Public endpoint."""
    return {"products": [], "total": 0}


@app.post("/api/products")
async def create_product(
    body: ProductCreate,
    token: str = Depends(oauth2_scheme)
):
    """Create a new product (admin only)."""
    return {"id": 1, "name": body.name, "price": body.price}


@app.get("/api/products/{product_id}")
async def get_product(product_id: int):
    """Get product details. Public endpoint."""
    return {"id": product_id, "name": "Sample Product", "price": 9.99}


@app.delete("/api/products/{product_id}")
async def delete_product(product_id: int, token: str = Depends(oauth2_scheme)):
    """Delete a product (admin only)."""
    return {"deleted": True}
