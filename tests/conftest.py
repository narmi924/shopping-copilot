from __future__ import annotations

import json
from pathlib import Path

import pytest

from shopping_copilot.agent import Agent


PRODUCTS = [
    {
        "parent_asin": "A_RED_COTTON_SHOE",
        "title": "Red Cotton Running Shoes",
        "categories": ["Clothing, Shoes & Jewelry", "Women", "Athletic Shoes"],
        "features": ["breathable cotton upper", "lightweight running trainer"],
        "details": {"Color": "Red", "Size": "8"},
        "store": "Stride Lab",
        "description": ["Comfortable shoes for running and gym workouts"],
        "price": 39.99,
        "average_rating": 4.6,
        "rating_number": 120,
    },
    {
        "parent_asin": "A_BLUE_LEATHER_SHOE",
        "title": "Blue Leather Walking Shoes",
        "categories": ["Clothing, Shoes & Jewelry", "Women", "Walking Shoes"],
        "features": ["genuine leather upper", "cushioned walking sole"],
        "details": {"Color": "Blue", "Size": "8"},
        "store": "Heritage Walk",
        "description": ["Classic blue everyday walking shoe"],
        "price": 49.99,
        "average_rating": 4.7,
        "rating_number": 95,
    },
    {
        "parent_asin": "A_GREEN_HIKING_SHOE",
        "title": "Green Waterproof Hiking Boots",
        "categories": ["Clothing, Shoes & Jewelry", "Men", "Hiking Boots"],
        "features": ["waterproof mesh", "outdoor trail grip"],
        "details": {"Color": "Green", "Material": "Mesh"},
        "store": "Trail Works",
        "description": ["Hiking footwear for wet outdoor trails"],
        "price": 69.5,
        "average_rating": 4.5,
        "rating_number": 150,
    },
    {
        "parent_asin": "B_BLACK_WOOL_COAT",
        "title": "Black Wool Winter Coat",
        "categories": ["Clothing, Shoes & Jewelry", "Women", "Coats"],
        "features": ["warm wool blend", "classic formal style"],
        "details": {"Color": "Black", "Material": "Wool"},
        "store": "North Wardrobe",
        "description": ["Warm coat for winter work commutes"],
        "price": 89.0,
        "average_rating": 4.8,
        "rating_number": 300,
    },
    {
        "parent_asin": "C_PINK_SILK_DRESS",
        "title": "Pink Silk Wedding Dress",
        "categories": ["Clothing, Shoes & Jewelry", "Women", "Dresses"],
        "features": ["soft silk fabric", "formal wedding style"],
        "details": {"Color": "Pink", "Size": "Medium"},
        "store": "Ceremony Studio",
        "description": ["Elegant dress for weddings and parties"],
        "price": 129.99,
        "average_rating": 4.4,
        "rating_number": 65,
    },
    {
        "parent_asin": "D_NAVY_TRAVEL_BACKPACK",
        "title": "Navy Nylon Travel Backpack",
        "categories": ["Clothing, Shoes & Jewelry", "Luggage", "Backpacks"],
        "features": ["lightweight nylon", "laptop compartment"],
        "details": {"Color": "Navy", "Capacity": "30L"},
        "store": "Carry On",
        "description": ["Backpack for business travel"],
        "price": 54.95,
        "average_rating": 4.9,
        "rating_number": 410,
    },
]


@pytest.fixture
def catalog_path(tmp_path: Path) -> Path:
    path = tmp_path / "catalog.jsonl"
    path.write_text("".join(json.dumps(product) + "\n" for product in PRODUCTS), encoding="utf-8")
    return path


@pytest.fixture
def agent(catalog_path: Path) -> Agent:
    return Agent(catalog_path)
