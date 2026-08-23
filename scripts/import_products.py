import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from datetime import datetime, timedelta
from app.database.connection import SessionLocal, init_db
from app.database.models import User, Product, ProductSize, ShoppingList, ShoppingItem, PurchaseHistory
from app.search.vector_service import vector_service

def seed_database():
    init_db()
    db = SessionLocal()

    try:
        print("Seeding expanded supermarket catalog products and sizes...")

        user = db.query(User).filter_by(id="default-user-id").first()
        if not user:
            user = User(id="default-user-id", name="Primary User")
            db.add(user)
            db.commit()

        # Comprehensive Everyday Supermarket Product Catalog
        catalog = [
            # ── 1. PERSONAL CARE & HYGIENE ──────────────────────────────────
            {
                "name": "Shampoo",
                "brand": "Pantene",
                "category": "Personal Care",
                "description": "Nourishing hair care shampoo",
                "sizes": [
                    {"size_value": "180ml", "unit": "ml", "is_default": False},
                    {"size_value": "340ml", "unit": "ml", "is_default": False},
                    {"size_value": "650ml", "unit": "ml", "is_default": True},
                ]
            },
            {
                "name": "Bath Soap",
                "brand": "Dove",
                "category": "Personal Care",
                "description": "Moisturizing bathing soap bar",
                "sizes": [
                    {"size_value": "75g", "unit": "g", "is_default": False},
                    {"size_value": "125g", "unit": "g", "is_default": True},
                    {"size_value": "3 pack", "unit": "pack", "is_default": False}
                ]
            },
            {
                "name": "Toothpaste",
                "brand": "Colgate",
                "category": "Personal Care",
                "description": "Strong teeth dental protection toothpaste",
                "sizes": [
                    {"size_value": "100g", "unit": "g", "is_default": False},
                    {"size_value": "150g", "unit": "g", "is_default": True},
                    {"size_value": "200g", "unit": "g", "is_default": False}
                ]
            },
            {
                "name": "Hand Wash",
                "brand": "Dettol",
                "category": "Personal Care",
                "description": "Antibacterial liquid hand wash refill",
                "sizes": [
                    {"size_value": "200ml", "unit": "ml", "is_default": False},
                    {"size_value": "750ml", "unit": "ml", "is_default": True}
                ]
            },
            {
                "name": "Body Lotion",
                "brand": "Nivea",
                "category": "Personal Care",
                "description": "Deep moisture body lotion cream",
                "sizes": [
                    {"size_value": "200ml", "unit": "ml", "is_default": False},
                    {"size_value": "400ml", "unit": "ml", "is_default": True}
                ]
            },
            {
                "name": "Hair Oil",
                "brand": "Parachute",
                "category": "Personal Care",
                "description": "Pure coconut hair oil",
                "sizes": [
                    {"size_value": "100ml", "unit": "ml", "is_default": False},
                    {"size_value": "300ml", "unit": "ml", "is_default": True},
                    {"size_value": "600ml", "unit": "ml", "is_default": False}
                ]
            },

            # ── 2. DAIRY & EGGS ─────────────────────────────────────────────
            {
                "name": "Milk",
                "brand": "Dairy Pure",
                "category": "Dairy",
                "description": "Fresh pasteurized whole milk",
                "sizes": [
                    {"size_value": "500ml", "unit": "ml", "is_default": False},
                    {"size_value": "1L", "unit": "L", "is_default": True}
                ]
            },
            {
                "name": "Butter",
                "brand": "Amul",
                "category": "Dairy",
                "description": "Pasteurized salted butter",
                "sizes": [
                    {"size_value": "100g", "unit": "g", "is_default": False},
                    {"size_value": "250g", "unit": "g", "is_default": False},
                    {"size_value": "500g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Eggs",
                "brand": "Farm Fresh",
                "category": "Dairy",
                "description": "Grade A large farm fresh eggs",
                "sizes": [
                    {"size_value": "6 pack", "unit": "pack", "is_default": False},
                    {"size_value": "12 pack", "unit": "pack", "is_default": True},
                    {"size_value": "30 pack", "unit": "pack", "is_default": False}
                ]
            },
            {
                "name": "Curd",
                "brand": "Amul",
                "category": "Dairy",
                "description": "Fresh creamy dahi curd",
                "sizes": [
                    {"size_value": "200g", "unit": "g", "is_default": False},
                    {"size_value": "400g", "unit": "g", "is_default": True},
                    {"size_value": "1kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Paneer",
                "brand": "Amul",
                "category": "Dairy",
                "description": "Fresh cottage cheese paneer block",
                "sizes": [
                    {"size_value": "200g", "unit": "g", "is_default": True},
                    {"size_value": "500g", "unit": "g", "is_default": False}
                ]
            },
            {
                "name": "Ghee",
                "brand": "Amul",
                "category": "Dairy",
                "description": "Pure cow ghee clarified butter",
                "sizes": [
                    {"size_value": "500ml", "unit": "ml", "is_default": False},
                    {"size_value": "1L", "unit": "L", "is_default": True}
                ]
            },
            {
                "name": "Buttermilk",
                "brand": "Mother Dairy",
                "category": "Dairy",
                "description": "Spiced refreshing masala chaach buttermilk",
                "sizes": [
                    {"size_value": "200ml", "unit": "ml", "is_default": False},
                    {"size_value": "500ml", "unit": "ml", "is_default": True}
                ]
            },
            {
                "name": "Cheese Slices",
                "brand": "Amul",
                "category": "Dairy",
                "description": "Processed cheese slices for sandwiches",
                "sizes": [
                    {"size_value": "100g", "unit": "g", "is_default": False},
                    {"size_value": "200g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Fresh Cream",
                "brand": "Amul",
                "category": "Dairy",
                "description": "Low fat fresh cooking cream",
                "sizes": [
                    {"size_value": "200ml", "unit": "ml", "is_default": True},
                    {"size_value": "1L", "unit": "L", "is_default": False}
                ]
            },
            {
                "name": "Flavored Milk",
                "brand": "Amul Kool",
                "category": "Dairy",
                "description": "Delicious chocolate and cardamom flavored milk bottle",
                "sizes": [
                    {"size_value": "200ml", "unit": "ml", "is_default": True}
                ]
            },

            # ── 3. STAPLES & FLOUR ──────────────────────────────────────────
            {
                "name": "Atta",
                "brand": "Aashirvaad",
                "category": "Staples",
                "description": "Whole wheat flour for roti and chapati",
                "sizes": [
                    {"size_value": "1kg", "unit": "kg", "is_default": False},
                    {"size_value": "5kg", "unit": "kg", "is_default": True},
                    {"size_value": "10kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Rice",
                "brand": "India Gate",
                "category": "Staples",
                "description": "Basmati rice grains for daily cooking",
                "sizes": [
                    {"size_value": "1kg", "unit": "kg", "is_default": True},
                    {"size_value": "5kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Basmati Rice",
                "brand": "India Gate Premium",
                "category": "Staples",
                "description": "Premium long grain basmati rice",
                "sizes": [
                    {"size_value": "1kg", "unit": "kg", "is_default": False},
                    {"size_value": "5kg", "unit": "kg", "is_default": True}
                ]
            },
            {
                "name": "Sona Masoori Rice",
                "brand": "Fortune",
                "category": "Staples",
                "description": "Lightweight raw rice for daily meals",
                "sizes": [
                    {"size_value": "5kg", "unit": "kg", "is_default": True},
                    {"size_value": "10kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Idli Rice",
                "brand": "Elite",
                "category": "Staples",
                "description": "Short grain rice for dosa and idli batter",
                "sizes": [
                    {"size_value": "1kg", "unit": "kg", "is_default": False},
                    {"size_value": "5kg", "unit": "kg", "is_default": True}
                ]
            },
            {
                "name": "Maida",
                "brand": "Aashirvaad",
                "category": "Staples",
                "description": "Refined wheat flour for baking and snacks",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": False},
                    {"size_value": "1kg", "unit": "kg", "is_default": True}
                ]
            },
            {
                "name": "Rava",
                "brand": "Rajdhani",
                "category": "Staples",
                "description": "Sooji semolina flour for upma and halwa",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True},
                    {"size_value": "1kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Besan",
                "brand": "Fortune",
                "category": "Staples",
                "description": "Gram flour made from ground chana dal",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True},
                    {"size_value": "1kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Poha",
                "brand": "Tata Sampann",
                "category": "Staples",
                "description": "Thick flattened rice flakes for breakfast",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Dalia",
                "brand": "MTR",
                "category": "Staples",
                "description": "Broken wheat dhalia grains",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Vermicelli",
                "brand": "Bambino",
                "category": "Staples",
                "description": "Roasted seviyan vermicelli noodles",
                "sizes": [
                    {"size_value": "400g", "unit": "g", "is_default": True}
                ]
            },

            # ── 4. PULSES & DAL ─────────────────────────────────────────────
            {
                "name": "Toor Dal",
                "brand": "Tata Sampann",
                "category": "Pulses & Dal",
                "description": "Unpolished arhar toor dal lentils",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": False},
                    {"size_value": "1kg", "unit": "kg", "is_default": True}
                ]
            },
            {
                "name": "Moong Dal",
                "brand": "Tata Sampann",
                "category": "Pulses & Dal",
                "description": "Yellow split moong dal",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": False},
                    {"size_value": "1kg", "unit": "kg", "is_default": True}
                ]
            },
            {
                "name": "Masoor Dal",
                "brand": "Fortune",
                "category": "Pulses & Dal",
                "description": "Red split masoor lentils",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True},
                    {"size_value": "1kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Urad Dal",
                "brand": "Tata Sampann",
                "category": "Pulses & Dal",
                "description": "White split urad dal for idli and dosa",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": False},
                    {"size_value": "1kg", "unit": "kg", "is_default": True}
                ]
            },
            {
                "name": "Chana Dal",
                "brand": "Fortune",
                "category": "Pulses & Dal",
                "description": "Split Bengal gram chana dal",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True},
                    {"size_value": "1kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Rajma",
                "brand": "Tata Sampann",
                "category": "Pulses & Dal",
                "description": "Red kidney beans for rajma curry",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True},
                    {"size_value": "1kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Kabuli Chana",
                "brand": "Tata Sampann",
                "category": "Pulses & Dal",
                "description": "Large white chickpeas for chole",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True},
                    {"size_value": "1kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Black Chana",
                "brand": "Fortune",
                "category": "Pulses & Dal",
                "description": "Whole brown Bengal gram chickpeas",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True}
                ]
            },

            # ── 5. COOKING OILS & GHEE ──────────────────────────────────────
            {
                "name": "Sunflower Oil",
                "brand": "Fortune",
                "category": "Oils & Ghee",
                "description": "Refined sunflower edible cooking oil",
                "sizes": [
                    {"size_value": "1L", "unit": "L", "is_default": True},
                    {"size_value": "5L", "unit": "L", "is_default": False}
                ]
            },
            {
                "name": "Mustard Oil",
                "brand": "Fortune Kachi Ghani",
                "category": "Oils & Ghee",
                "description": "Cold pressed kachi ghani mustard oil",
                "sizes": [
                    {"size_value": "1L", "unit": "L", "is_default": True},
                    {"size_value": "5L", "unit": "L", "is_default": False}
                ]
            },
            {
                "name": "Groundnut Oil",
                "brand": "Saffola",
                "category": "Oils & Ghee",
                "description": "Filtered peanut cooking oil",
                "sizes": [
                    {"size_value": "1L", "unit": "L", "is_default": True}
                ]
            },
            {
                "name": "Rice Bran Oil",
                "brand": "Fortune Physically Refined",
                "category": "Oils & Ghee",
                "description": "Heart healthy rice bran cooking oil",
                "sizes": [
                    {"size_value": "1L", "unit": "L", "is_default": True},
                    {"size_value": "5L", "unit": "L", "is_default": False}
                ]
            },
            {
                "name": "Coconut Oil",
                "brand": "Parachute 100% Pure",
                "category": "Oils & Ghee",
                "description": "Pure edible coconut oil for cooking and hair",
                "sizes": [
                    {"size_value": "500ml", "unit": "ml", "is_default": True},
                    {"size_value": "1L", "unit": "L", "is_default": False}
                ]
            },
            {
                "name": "Olive Oil",
                "brand": "Borges",
                "category": "Oils & Ghee",
                "description": "Extra virgin olive oil for salad and cooking",
                "sizes": [
                    {"size_value": "500ml", "unit": "ml", "is_default": True},
                    {"size_value": "1L", "unit": "L", "is_default": False}
                ]
            },

            # ── 6. SPICES & MASALA ──────────────────────────────────────────
            {
                "name": "Turmeric Powder",
                "brand": "MDH",
                "category": "Spices",
                "description": "Haldi powder pure ground turmeric",
                "sizes": [
                    {"size_value": "100g", "unit": "g", "is_default": False},
                    {"size_value": "200g", "unit": "g", "is_default": True},
                    {"size_value": "500g", "unit": "g", "is_default": False}
                ]
            },
            {
                "name": "Red Chilli Powder",
                "brand": "Everest",
                "category": "Spices",
                "description": "Spicy tikhalal red chilli powder",
                "sizes": [
                    {"size_value": "100g", "unit": "g", "is_default": False},
                    {"size_value": "200g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Coriander Powder",
                "brand": "Everest Dhaniya",
                "category": "Spices",
                "description": "Aromatic dhaniya powder ground coriander",
                "sizes": [
                    {"size_value": "100g", "unit": "g", "is_default": False},
                    {"size_value": "200g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Cumin Seeds",
                "brand": "Tata Sampann",
                "category": "Spices",
                "description": "Whole jeera cumin seeds",
                "sizes": [
                    {"size_value": "100g", "unit": "g", "is_default": True},
                    {"size_value": "200g", "unit": "g", "is_default": False}
                ]
            },
            {
                "name": "Mustard Seeds",
                "brand": "Catch",
                "category": "Spices",
                "description": "Small black mustard seeds rai for tadka seasoning",
                "sizes": [
                    {"size_value": "100g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Garam Masala",
                "brand": "Everest",
                "category": "Spices",
                "description": "Blended spice powder for Indian dishes",
                "sizes": [
                    {"size_value": "50g", "unit": "g", "is_default": False},
                    {"size_value": "100g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Sambar Powder",
                "brand": "MTR",
                "category": "Spices",
                "description": "Authentic South Indian sambhar masala powder",
                "sizes": [
                    {"size_value": "100g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Black Pepper",
                "brand": "Catch Whole",
                "category": "Spices",
                "description": "Whole black peppercorns kali mirch",
                "sizes": [
                    {"size_value": "100g", "unit": "g", "is_default": True}
                ]
            },

            # ── 7. SNACKS & NAMKEEN ─────────────────────────────────────────
            {
                "name": "Potato Chips",
                "brand": "Lay's Magic Masala",
                "category": "Snacks",
                "description": "Crispy salted potato chips packet",
                "sizes": [
                    {"size_value": "50g", "unit": "g", "is_default": False},
                    {"size_value": "90g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Aloo Bhujia",
                "brand": "Haldiram's",
                "category": "Snacks",
                "description": "Crispy potato and gram flour bhujia namkeen",
                "sizes": [
                    {"size_value": "150g", "unit": "g", "is_default": False},
                    {"size_value": "400g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Banana Chips",
                "brand": "Beyond Snack",
                "category": "Snacks",
                "description": "Crispy salted raw banana wafers",
                "sizes": [
                    {"size_value": "100g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Murukku",
                "brand": "Grand Sweets",
                "category": "Snacks",
                "description": "Traditional crunchy rice flour chakli murukku",
                "sizes": [
                    {"size_value": "200g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Popcorn",
                "brand": "Act II Butter",
                "category": "Snacks",
                "description": "Instant microwave butter popcorn pouch",
                "sizes": [
                    {"size_value": "150g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Salted Peanuts",
                "brand": "Haldiram's",
                "category": "Snacks",
                "description": "Crunchy roasted salted peanuts",
                "sizes": [
                    {"size_value": "200g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Roasted Chana",
                "brand": "Tong Garden",
                "category": "Snacks",
                "description": "Healthy salted roasted chickpeas",
                "sizes": [
                    {"size_value": "200g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Dry Fruits Mix",
                "brand": "Happilo Premium",
                "category": "Snacks",
                "description": "Almonds, cashews, raisins, and walnuts mix",
                "sizes": [
                    {"size_value": "250g", "unit": "g", "is_default": True},
                    {"size_value": "500g", "unit": "g", "is_default": False}
                ]
            },

            # ── 8. BISCUITS & COOKIES ───────────────────────────────────────
            {
                "name": "Glucose Biscuits",
                "brand": "Parle-G",
                "category": "Biscuits",
                "description": "Classic glucose tea biscuits",
                "sizes": [
                    {"size_value": "250g", "unit": "g", "is_default": True},
                    {"size_value": "800g family pack", "unit": "pack", "is_default": False}
                ]
            },
            {
                "name": "Marie Biscuits",
                "brand": "Britannia Marie Gold",
                "category": "Biscuits",
                "description": "Crispy tea dunking Marie biscuits",
                "sizes": [
                    {"size_value": "250g", "unit": "g", "is_default": True},
                    {"size_value": "1kg mega pack", "unit": "pack", "is_default": False}
                ]
            },
            {
                "name": "Cream Biscuits",
                "brand": "Oreo",
                "category": "Biscuits",
                "description": "Chocolate cream sandwich cookies",
                "sizes": [
                    {"size_value": "120g", "unit": "g", "is_default": True},
                    {"size_value": "300g family pack", "unit": "pack", "is_default": False}
                ]
            },
            {
                "name": "Digestive Biscuits",
                "brand": "NutriChoice",
                "category": "Biscuits",
                "description": "High fibre wheat digestive biscuits",
                "sizes": [
                    {"size_value": "100g", "unit": "g", "is_default": False},
                    {"size_value": "250g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Salt Crackers",
                "brand": "Monaco",
                "category": "Biscuits",
                "description": "Light salted snack crackers",
                "sizes": [
                    {"size_value": "200g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Butter Cookies",
                "brand": "Unibic",
                "category": "Biscuits",
                "description": "Rich butter baked cookies",
                "sizes": [
                    {"size_value": "150g", "unit": "g", "is_default": True}
                ]
            },

            # ── 9. BREAKFAST & SPREADS ───────────────────────────────────────
            {
                "name": "Cornflakes",
                "brand": "Kellogg's Original",
                "category": "Breakfast",
                "description": "Crispy toasted corn flakes breakfast cereal",
                "sizes": [
                    {"size_value": "250g", "unit": "g", "is_default": False},
                    {"size_value": "475g", "unit": "g", "is_default": True},
                    {"size_value": "875g", "unit": "g", "is_default": False}
                ]
            },
            {
                "name": "Rolled Oats",
                "brand": "Quaker",
                "category": "Breakfast",
                "description": "100% whole grain oats porridge",
                "sizes": [
                    {"size_value": "400g", "unit": "g", "is_default": False},
                    {"size_value": "1kg", "unit": "kg", "is_default": True}
                ]
            },
            {
                "name": "Muesli",
                "brand": "Kellogg's Fruit & Nut",
                "category": "Breakfast",
                "description": "Multi-grain muesli with dried fruits and nuts",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Chocos",
                "brand": "Kellogg's",
                "category": "Breakfast",
                "description": "Crunchy chocolate wheat breakfast cereal scoops",
                "sizes": [
                    {"size_value": "250g", "unit": "g", "is_default": False},
                    {"size_value": "375g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Peanut Butter",
                "brand": "Sundrop Crunchy",
                "category": "Breakfast",
                "description": "High protein roasted peanut butter spread",
                "sizes": [
                    {"size_value": "350g", "unit": "g", "is_default": True},
                    {"size_value": "900g", "unit": "g", "is_default": False}
                ]
            },
            {
                "name": "Honey",
                "brand": "Dabur 100% Pure",
                "category": "Breakfast",
                "description": "Pure natural honey bottle",
                "sizes": [
                    {"size_value": "250g", "unit": "g", "is_default": False},
                    {"size_value": "500g", "unit": "g", "is_default": True},
                    {"size_value": "1kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Jam",
                "brand": "Kissan Mixed Fruit",
                "category": "Breakfast",
                "description": "Delicious mixed fruit jam spread for bread",
                "sizes": [
                    {"size_value": "200g", "unit": "g", "is_default": False},
                    {"size_value": "500g", "unit": "g", "is_default": True}
                ]
            },

            # ── 10. BAKERY & BREAD ──────────────────────────────────────────
            {
                "name": "Bread",
                "brand": "Britannia Whole Wheat",
                "category": "Bakery",
                "description": "100% whole wheat sliced bread loaf",
                "sizes": [
                    {"size_value": "400g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Brown Bread",
                "brand": "Modern",
                "category": "Bakery",
                "description": "Healthy brown bread loaf",
                "sizes": [
                    {"size_value": "400g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Multigrain Bread",
                "brand": "English Oven",
                "category": "Bakery",
                "description": "High fibre 7 grain bread loaf",
                "sizes": [
                    {"size_value": "400g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Burger Buns",
                "brand": "English Oven",
                "category": "Bakery",
                "description": "Soft sesame seed burger buns",
                "sizes": [
                    {"size_value": "2 pack", "unit": "pack", "is_default": True}
                ]
            },
            {
                "name": "Pav",
                "brand": "Modern",
                "category": "Bakery",
                "description": "Soft ladi pav buns for vada pav and bhaji",
                "sizes": [
                    {"size_value": "6 pack", "unit": "pack", "is_default": True}
                ]
            },
            {
                "name": "Toast Rusk",
                "brand": "Britannia Toastea Premium",
                "category": "Bakery",
                "description": "Crunchy elaichi tea toast rusk",
                "sizes": [
                    {"size_value": "182g", "unit": "g", "is_default": True}
                ]
            },

            # ── 11. BEVERAGES ───────────────────────────────────────────────
            {
                "name": "Coffee",
                "brand": "Nescafe Classic",
                "category": "Beverages",
                "description": "Instant pure coffee powder",
                "sizes": [
                    {"size_value": "50g", "unit": "g", "is_default": False},
                    {"size_value": "100g", "unit": "g", "is_default": True},
                    {"size_value": "200g", "unit": "g", "is_default": False}
                ]
            },
            {
                "name": "Black Tea",
                "brand": "Tata Tea Gold",
                "category": "Beverages",
                "description": "Rich flavor long leaf black tea leaves",
                "sizes": [
                    {"size_value": "250g", "unit": "g", "is_default": False},
                    {"size_value": "500g", "unit": "g", "is_default": True},
                    {"size_value": "1kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Green Tea",
                "brand": "Lipton Lemon",
                "category": "Beverages",
                "description": "Zero calorie green tea bags with lemon flavor",
                "sizes": [
                    {"size_value": "25 bags", "unit": "pack", "is_default": True},
                    {"size_value": "100 bags", "unit": "pack", "is_default": False}
                ]
            },
            {
                "name": "Drinking Water",
                "brand": "Bisleri",
                "category": "Beverages",
                "description": "Purified packaged mineral drinking water bottle",
                "sizes": [
                    {"size_value": "1L", "unit": "L", "is_default": True},
                    {"size_value": "5L", "unit": "L", "is_default": False}
                ]
            },
            {
                "name": "Mango Juice",
                "brand": "Real Fruit Power",
                "category": "Beverages",
                "description": "Delicious mango fruit nectar drink",
                "sizes": [
                    {"size_value": "1L", "unit": "L", "is_default": True}
                ]
            },
            {
                "name": "Orange Juice",
                "brand": "Tropicana 100%",
                "category": "Beverages",
                "description": "Pure orange juice with pulp no added sugar",
                "sizes": [
                    {"size_value": "1L", "unit": "L", "is_default": True}
                ]
            },
            {
                "name": "Coconut Water",
                "brand": "Raw Pressery",
                "category": "Beverages",
                "description": "100% natural tender coconut water",
                "sizes": [
                    {"size_value": "200ml", "unit": "ml", "is_default": True}
                ]
            },
            {
                "name": "Cola Drink",
                "brand": "Coca-Cola",
                "category": "Beverages",
                "description": "Carbonated soft drink bottle",
                "sizes": [
                    {"size_value": "750ml", "unit": "ml", "is_default": True},
                    {"size_value": "2L", "unit": "L", "is_default": False}
                ]
            },

            # ── 12. PACKAGED FOOD ───────────────────────────────────────────
            {
                "name": "Instant Noodles",
                "brand": "Maggi 2-Minute",
                "category": "Packaged Food",
                "description": "Masala instant wheat noodles",
                "sizes": [
                    {"size_value": "70g single", "unit": "pack", "is_default": False},
                    {"size_value": "280g 4-pack", "unit": "pack", "is_default": True},
                    {"size_value": "560g 8-pack", "unit": "pack", "is_default": False}
                ]
            },
            {
                "name": "Pasta",
                "brand": "Bambino Penne",
                "category": "Packaged Food",
                "description": "Durum wheat semolina penne pasta",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Tomato Ketchup",
                "brand": "Kissan Fresh Tomato",
                "category": "Packaged Food",
                "description": "Rich tomato ketchup sauce squeeze bottle",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True},
                    {"size_value": "1kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Mayonnaise",
                "brand": "FunFoods Veg",
                "category": "Packaged Food",
                "description": "Creamy eggless mayonnaise spread",
                "sizes": [
                    {"size_value": "250g", "unit": "g", "is_default": False},
                    {"size_value": "500g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Soy Sauce",
                "brand": "Ching's Secret",
                "category": "Packaged Food",
                "description": "Dark soy sauce for cooking Chinese dishes",
                "sizes": [
                    {"size_value": "210ml", "unit": "ml", "is_default": True}
                ]
            },
            {
                "name": "Mango Pickle",
                "brand": "Mother's Recipe",
                "category": "Packaged Food",
                "description": "Traditional spicy Gujarati raw mango pickle",
                "sizes": [
                    {"size_value": "300g", "unit": "g", "is_default": False},
                    {"size_value": "500g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Ready-to-Eat Dal Makhani",
                "brand": "MTR",
                "category": "Packaged Food",
                "description": "Instant heat and eat creamy dal makhani pouch",
                "sizes": [
                    {"size_value": "300g", "unit": "g", "is_default": True}
                ]
            },

            # ── 13. FRUITS & VEGETABLES ─────────────────────────────────────
            {
                "name": "Apples",
                "brand": "Fresh Harvest",
                "category": "Fruits & Vegetables",
                "description": "Crisp red Royal Gala apples",
                "sizes": [
                    {"size_value": "1kg", "unit": "kg", "is_default": True}
                ]
            },
            {
                "name": "Bananas",
                "brand": "Fresh Harvest",
                "category": "Fruits & Vegetables",
                "description": "Fresh sweet Robusta yellow bananas",
                "sizes": [
                    {"size_value": "6 pcs", "unit": "piece", "is_default": False},
                    {"size_value": "1 dozen", "unit": "dozen", "is_default": True}
                ]
            },
            {
                "name": "Oranges",
                "brand": "Fresh Harvest",
                "category": "Fruits & Vegetables",
                "description": "Juicy sweet Nagpur oranges",
                "sizes": [
                    {"size_value": "1kg", "unit": "kg", "is_default": True}
                ]
            },
            {
                "name": "Tomatoes",
                "brand": "Fresh Harvest",
                "category": "Fruits & Vegetables",
                "description": "Ripe red hybrid cooking tomatoes",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": False},
                    {"size_value": "1kg", "unit": "kg", "is_default": True}
                ]
            },
            {
                "name": "Potatoes",
                "brand": "Fresh Harvest",
                "category": "Fruits & Vegetables",
                "description": "Fresh cooking potatoes aloo",
                "sizes": [
                    {"size_value": "1kg", "unit": "kg", "is_default": True},
                    {"size_value": "2kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Onions",
                "brand": "Fresh Harvest",
                "category": "Fruits & Vegetables",
                "description": "Fresh red onions pyaz",
                "sizes": [
                    {"size_value": "1kg", "unit": "kg", "is_default": True},
                    {"size_value": "2kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Carrots",
                "brand": "Fresh Harvest",
                "category": "Fruits & Vegetables",
                "description": "Fresh crunchy orange carrots gajar",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Spinach",
                "brand": "Fresh Harvest",
                "category": "Fruits & Vegetables",
                "description": "Fresh green palak spinach leaves",
                "sizes": [
                    {"size_value": "1 bunch", "unit": "bunch", "is_default": True}
                ]
            },
            {
                "name": "Lady Finger",
                "brand": "Fresh Harvest",
                "category": "Fruits & Vegetables",
                "description": "Tender green bhindi okra lady finger",
                "sizes": [
                    {"size_value": "250g", "unit": "g", "is_default": False},
                    {"size_value": "500g", "unit": "g", "is_default": True}
                ]
            },
            {
                "name": "Green Peas",
                "brand": "Safal Frozen",
                "category": "Fruits & Vegetables",
                "description": "Tender sweet frozen green peas matar",
                "sizes": [
                    {"size_value": "500g", "unit": "g", "is_default": True},
                    {"size_value": "1kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Lemons",
                "brand": "Fresh Harvest",
                "category": "Fruits & Vegetables",
                "description": "Juicy yellow lemons nimbu",
                "sizes": [
                    {"size_value": "4 pcs", "unit": "piece", "is_default": True}
                ]
            },

            # ── 14. HOME CARE & CLEANING ────────────────────────────────────
            {
                "name": "Laundry Detergent Powder",
                "brand": "Surf Excel Easy Wash",
                "category": "Home Care",
                "description": "Stain removal laundry washing powder",
                "sizes": [
                    {"size_value": "1kg", "unit": "kg", "is_default": True},
                    {"size_value": "3kg", "unit": "kg", "is_default": False}
                ]
            },
            {
                "name": "Dishwashing Liquid",
                "brand": "Vim Gel",
                "category": "Home Care",
                "description": "Concentrated lemon dishwash liquid gel",
                "sizes": [
                    {"size_value": "250ml", "unit": "ml", "is_default": False},
                    {"size_value": "750ml", "unit": "ml", "is_default": True}
                ]
            },
            {
                "name": "Floor Cleaner",
                "brand": "Lizol Citrus",
                "category": "Home Care",
                "description": "Disinfectant surface and floor cleaner liquid",
                "sizes": [
                    {"size_value": "500ml", "unit": "ml", "is_default": False},
                    {"size_value": "1L", "unit": "L", "is_default": True},
                    {"size_value": "2L", "unit": "L", "is_default": False}
                ]
            },
            {
                "name": "Toilet Cleaner",
                "brand": "Harpic Power Plus",
                "category": "Home Care",
                "description": "Disinfectant toilet bowl cleaner gel",
                "sizes": [
                    {"size_value": "500ml", "unit": "ml", "is_default": False},
                    {"size_value": "1L", "unit": "L", "is_default": True}
                ]
            },
            {
                "name": "Glass Cleaner",
                "brand": "Colin Spray",
                "category": "Home Care",
                "description": "Shine glass and surface cleaner spray bottle",
                "sizes": [
                    {"size_value": "500ml", "unit": "ml", "is_default": True}
                ]
            },

            # ── 15. HOUSEHOLD ESSENTIALS ────────────────────────────────────
            {
                "name": "Garbage Bags",
                "brand": "ShineX",
                "category": "Household Essentials",
                "description": "Medium black disposable trash garbage bags roll",
                "sizes": [
                    {"size_value": "30 count", "unit": "pack", "is_default": True}
                ]
            },
            {
                "name": "Tissue Paper",
                "brand": "Origami",
                "category": "Household Essentials",
                "description": "2 ply soft paper facial tissues box",
                "sizes": [
                    {"size_value": "100 pulls", "unit": "pack", "is_default": True}
                ]
            },
            {
                "name": "Aluminium Foil",
                "brand": "Freshwrap",
                "category": "Household Essentials",
                "description": "Food safe wrapping aluminium foil roll",
                "sizes": [
                    {"size_value": "9 meters", "unit": "pack", "is_default": False},
                    {"size_value": "18 meters", "unit": "pack", "is_default": True}
                ]
            },
            {
                "name": "Kitchen Towels",
                "brand": "Origami",
                "category": "Household Essentials",
                "description": "Absorbent 2 ply kitchen paper towel rolls",
                "sizes": [
                    {"size_value": "2 rolls", "unit": "pack", "is_default": True}
                ]
            },
            {
                "name": "Scrub Pads",
                "brand": "Scotch-Brite",
                "category": "Household Essentials",
                "description": "Heavy duty utensil scrubbing pads",
                "sizes": [
                    {"size_value": "3 pack", "unit": "pack", "is_default": True}
                ]
            },

            # ── 16. BABY CARE ───────────────────────────────────────────────
            {
                "name": "Baby Diapers",
                "brand": "Pampers All Night",
                "category": "Baby Care",
                "description": "Soft absorbent pant style baby diapers",
                "sizes": [
                    {"size_value": "M size 44 pack", "unit": "pack", "is_default": True},
                    {"size_value": "L size 38 pack", "unit": "pack", "is_default": False}
                ]
            },
            {
                "name": "Baby Wipes",
                "brand": "Huggies Gentle",
                "category": "Baby Care",
                "description": "Moist alcohol free baby wet wipes",
                "sizes": [
                    {"size_value": "72 count", "unit": "pack", "is_default": True}
                ]
            }
        ]

        added_count = 0
        skipped_count = 0

        for item_data in catalog:
            existing = db.query(Product).filter(Product.name.ilike(item_data["name"])).first()
            if not existing:
                prod = Product(
                    name=item_data["name"],
                    brand=item_data["brand"],
                    category=item_data["category"],
                    description=item_data["description"]
                )
                db.add(prod)
                db.flush()

                for s_data in item_data["sizes"]:
                    ps = ProductSize(
                        product_id=prod.id,
                        size_value=s_data["size_value"],
                        unit=s_data["unit"],
                        is_default=s_data["is_default"]
                    )
                    db.add(ps)

                # Index product vectors into Qdrant & local store
                vector_service.register_product_embedding(
                    product_id=prod.id,
                    name=prod.name,
                    brand=prod.brand,
                    category=prod.category,
                    description=prod.description
                )
                added_count += 1
            else:
                skipped_count += 1

        db.commit()
        total_products = db.query(Product).count()
        print(f"Catalog Seeding Completed! Added: {added_count}, Skipped (Already Existed): {skipped_count}, Total Catalog Products: {total_products}")

        # Seed Completed Shopping Lists for Co-purchase (Bread + Jam pattern)
        print("Seeding sample completed shopping lists for co-purchase history...")
        
        existing_completed = db.query(ShoppingList).filter_by(user_id=user.id, status="COMPLETED").count()
        if existing_completed == 0:
            past_lists_data = [
                ["Bread", "Jam", "Milk"],
                ["Bread", "Jam", "Eggs"],
                ["Bread", "Jam", "Milk"]
            ]

            now = datetime.utcnow()
            for idx, items_names in enumerate(past_lists_data):
                created_time = now - timedelta(days=(3 - idx))
                sl = ShoppingList(user_id=user.id, status="COMPLETED", created_at=created_time, updated_at=created_time)
                db.add(sl)
                db.flush()

                for p_name in items_names:
                    prod = db.query(Product).filter(Product.name.ilike(p_name)).first()
                    si = ShoppingItem(
                        list_id=sl.id,
                        product_id=prod.id if prod else None,
                        product_name=p_name,
                        quantity=1,
                        status="PURCHASED",
                        created_at=created_time
                    )
                    db.add(si)

                    size_val = "650ml" if p_name == "Shampoo" else "1L" if p_name == "Milk" else None
                    ph = PurchaseHistory(
                        user_id=user.id,
                        list_id=sl.id,
                        product_id=prod.id if prod else None,
                        product_name=p_name,
                        size=size_val,
                        purchased_at=created_time
                    )
                    db.add(ph)

            db.commit()
            print("Successfully seeded 3 completed shopping lists for co-purchase analysis.")

        # Seed Shampoo Purchase History (650ml, 650ml, 340ml) for 2/3 preference rule testing
        shampoo_prod = db.query(Product).filter(Product.name.ilike("Shampoo")).first()
        if shampoo_prod:
            shampoo_history_count = db.query(PurchaseHistory).filter(PurchaseHistory.product_name.ilike("Shampoo")).count()
            if shampoo_history_count == 0:
                shampoo_sizes = ["650ml", "650ml", "340ml"]
                now = datetime.utcnow()
                for idx, sz in enumerate(shampoo_sizes):
                    ph = PurchaseHistory(
                        user_id=user.id,
                        product_id=shampoo_prod.id,
                        product_name="Shampoo",
                        size=sz,
                        purchased_at=now - timedelta(days=10 - idx)
                    )
                    db.add(ph)
                db.commit()
                print("Seeded Shampoo purchase history (650ml, 650ml, 340ml) for size preference engine.")

        print("Database seeding completed cleanly!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
