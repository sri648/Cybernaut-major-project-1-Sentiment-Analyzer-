"""HTTP route definitions for the backend API."""

from datetime import datetime

from flask import Blueprint, jsonify, request

from app.database import database
from app.scraper import get_reviews
from app.sentiment import analyze_review
from app.utils import clean_text

api = Blueprint("api", __name__)


@api.get("/health")
def health_check():
    """Return a lightweight readiness response for local and cloud checks."""
    return jsonify({"status": "ok", "message": "Flask API is running"})


def _summary(product, reviews):
    counts = {"Positive": 0, "Negative": 0, "Neutral": 0}
    for review in reviews:
        counts[review["sentiment"]] += 1
    ratings = [review["rating"] for review in reviews]
    return {
        "product": product,
        "total_reviews": len(reviews),
        "positive": counts["Positive"],
        "negative": counts["Negative"],
        "neutral": counts["Neutral"],
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
        "reviews": reviews,
    }


@api.get("/search")
def search_product():
    product = request.args.get("product", "").strip()
    if not product:
        return jsonify({"error": "Please provide a product name."}), 400
    try:
        raw_reviews = get_reviews(product)
        reviews = []
        for item in raw_reviews:
            text = clean_text(item.get("review", ""))
            if not text:
                continue
            result = analyze_review(text)
            reviews.append({
                "product": product,
                "text": text,
                "review": text,
                "rating": float(item.get("rating", 0)),
                "date": item.get("date", ""),
                **result,
            })
        if not reviews:
            return jsonify({"error": "No reviews found for this product."}), 404
        database.save_product(product, "Demo catalog")
        database.save_reviews(reviews)
        summary = _summary(product, reviews)
        database.save_history({"product": product, "date": datetime.utcnow().isoformat(), "review_count": len(reviews), "sentiment": max(("Positive", summary["positive"]), ("Negative", summary["negative"]), ("Neutral", summary["neutral"]), key=lambda item: item[1])[0], "average_rating": summary["average_rating"]})
        return jsonify(summary)
    except Exception as error:
        return jsonify({"error": f"Unable to analyze reviews: {error}"}), 500


@api.get("/products")
def products():
    return jsonify({"products": database.list_products()})


@api.get("/products/<product_id>")
def product_detail(product_id):
    item = next((product for product in database.list_products() if product.get("_id") == product_id), None)
    if not item:
        return jsonify({"error": "Product not found."}), 404
    item["reviews"] = database.list_reviews(item["name"])
    return jsonify(item)


@api.post("/products")
def create_product():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    if not name:
        return jsonify({"error": "Product name is required."}), 400
    return jsonify(database.save_product(name, payload.get("source", "Manual import"))), 201


@api.delete("/products/<product_id>")
def delete_product(product_id):
    products = database.list_products()
    target = next((product for product in products if product.get("_id") == product_id), None)
    if not target:
        return jsonify({"error": "Product not found."}), 404
    if database.client:
        from bson import ObjectId
        if not ObjectId.is_valid(product_id):
            return jsonify({"error": "Invalid product ID."}), 400
        database.db.products.delete_one({"_id": ObjectId(product_id)})
    else:
        database.products.remove(target)
    return jsonify({"message": "Product deleted."})


@api.get("/reviews")
def reviews():
    product = request.args.get("product", "").strip() or None
    return jsonify({"reviews": database.list_reviews(product)})


@api.post("/reviews")
def create_review():
    payload = request.get_json(silent=True) or {}
    product = str(payload.get("product", "")).strip()
    text = clean_text(payload.get("review_text", payload.get("text", "")))
    if not product or not text:
        return jsonify({"error": "Product and review text are required."}), 400
    review = {"product": product, "text": text, "review": text, "rating": float(payload.get("rating", 0)), "date": payload.get("date", datetime.utcnow().date().isoformat()), **analyze_review(text)}
    database.save_reviews([review])
    return jsonify(review), 201


@api.delete("/reviews/<review_id>")
def delete_review(review_id):
    if not database.delete_review(review_id):
        return jsonify({"error": "Review not found."}), 404
    return jsonify({"message": "Review deleted."})


@api.post("/sentiment/analyze")
def analyze_sentiment():
    payload = request.get_json(silent=True) or {}
    text = clean_text(payload.get("text", ""))
    if not text:
        return jsonify({"error": "Review text is required."}), 400
    return jsonify({"text": text, **analyze_review(text), "model_note": "VADER NLP model output; not a guaranteed measure of opinion."})


@api.post("/sentiment/bulk")
def bulk_sentiment():
    payload = request.get_json(silent=True) or {}
    texts = payload.get("texts", [])
    if not isinstance(texts, list):
        return jsonify({"error": "texts must be an array."}), 400
    return jsonify({"results": [{"text": clean_text(text), **analyze_review(clean_text(text))} for text in texts if clean_text(text)]})


@api.post("/scraper/start")
def start_scraper():
    payload = request.get_json(silent=True) or {}
    product = str(payload.get("product", "")).strip()
    if not product:
        return jsonify({"error": "Product name is required for demo import."}), 400
    raw_reviews = get_reviews(product)
    return jsonify({"status": "completed", "mode": "demo", "product": product, "reviews_collected": len(raw_reviews), "reviews": raw_reviews, "message": "Demo data imported. Live scraping remains opt-in and must respect site policies."})


@api.get("/sentiment/<product>")
def sentiment(product):
    items = database.list_reviews(product)
    summary = _summary(product, items)
    return jsonify({key: summary[key] for key in ("product", "total_reviews", "positive", "negative", "neutral")})


@api.get("/analytics/<product>")
def analytics(product):
    items = database.list_reviews(product)
    rating_distribution = {str(rating): sum(1 for item in items if item["rating"] == rating) for rating in range(1, 6)}
    sentiment_trend = [{"date": item["date"], "score": item["score"]} for item in items]
    return jsonify({
        "product": product,
        "rating_distribution": rating_distribution,
        "sentiment_trend": sentiment_trend,
        "word_frequency": database.word_frequency(product),
    })


@api.get("/analytics/overview")
def analytics_overview():
    return jsonify(database.overview())


@api.get("/analytics/sentiment")
def analytics_sentiment():
    overview = database.overview()
    return jsonify({"distribution": {"Positive": overview["positive"], "Negative": overview["negative"], "Neutral": overview["neutral"]}, "by_product": [{"product": item["name"], "reviews": len(database.list_reviews(item["name"]))} for item in database.list_products()]})


@api.get("/analytics/trends")
def analytics_trends():
    reviews = database.list_reviews()
    return jsonify({"trends": [{"date": item.get("date", ""), "score": item.get("score", 0), "rating": item.get("rating", 0)} for item in reviews]})


@api.get("/history")
def history():
    return jsonify({"history": database.list_history()})


@api.delete("/history/<history_id>")
def delete_history(history_id):
    if not database.delete_history(history_id):
        return jsonify({"error": "History item not found."}), 404
    return jsonify({"message": "History item deleted."})


@api.post("/favorites")
def toggle_favorite():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    if not name:
        return jsonify({"error": "Product name is required."}), 400
    added = database.toggle_favorite({"name": name, "rating": payload.get("rating", 0), "sentiment": payload.get("sentiment", "Neutral"), "review_count": payload.get("review_count", 0)})
    return jsonify({"favorite": added})


@api.get("/favorites")
def favorites():
    return jsonify({"favorites": database.list_favorites()})
