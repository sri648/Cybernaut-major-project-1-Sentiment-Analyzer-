"""Seed the demo catalog with ten products and fifty analyzed reviews."""

from app import create_app
from app.database import database
from app.scraper import get_reviews
from app.sentiment import analyze_review
from app.utils import clean_text

PRODUCTS = [
    "iPhone 15", "Samsung Galaxy S24", "OnePlus 12", "Dell Laptop", "Sony Headphones",
    "Kindle Paperwhite", "Nintendo Switch", "Logitech MX Master", "Dyson Vacuum", "Instant Pot",
]


def seed():
    create_app()
    for product in PRODUCTS:
        database.save_product(product, "Demo catalog")
        reviews = []
        for item in get_reviews(product):
            text = clean_text(item["review"])
            reviews.append({"product": product, "text": text, "review": text, "rating": item["rating"], "date": item["date"], **analyze_review(text)})
        database.save_reviews(reviews)
    print(f"Seeded {len(PRODUCTS)} products and {len(database.reviews)} reviews.")


if __name__ == "__main__":
    seed()