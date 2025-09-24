import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict
import asyncpg
from crud import order as order_crud
from crud import product as product_crud
from core.pkgs.database import connection_pool
import os
import pickle
from core.utils.enums import ModelPath



async def train_and_cache_model():
    """
    Fetches purchase history, builds the item-item similarity model,
    and caches it to a file.
    """
    print("Starting recommendation model training...")
    pool = await connection_pool.get_pool()
    async with pool.acquire() as db:
        purchase_history = await order_crud.get_all_purchase_history(db)
        if not purchase_history:
            print("No purchase history found. Skipping model training.")
            return

        df = pd.DataFrame(purchase_history)
        df['purchased'] = 1

        # Create the user-item matrix
        user_item_matrix = pd.crosstab(df['user_id'], df['product_id'], df['purchased'], aggfunc='sum').fillna(0)

        # Calculate item-item similarity using cosine similarity
        item_similarity_matrix = cosine_similarity(user_item_matrix.T)

        # Create a mapping from product_id to matrix index and vice-versa
        product_ids = user_item_matrix.columns
        product_id_to_idx = {product_id: i for i, product_id in enumerate(product_ids)}

        model_data = {
            "item_similarity": item_similarity_matrix,
            "product_ids": product_ids,
            "product_id_to_idx": product_id_to_idx
        }

        # Ensure cache directory exists
        os.makedirs(os.path.dirname(ModelPath.MODEL_CACHE_PATH), exist_ok=True)

        # Cache the model data
        with open(ModelPath.MODEL_CACHE_PATH, 'wb') as f:
            pickle.dump(model_data, f)
        
        print(f"Model training complete. Cached to {ModelPath.MODEL_CACHE_PATH}")

def load_model_from_cache() -> Dict:
    """Loads the pre-computed model from cache."""
    if not os.path.exists(ModelPath.MODEL_CACHE_PATH):
        return None
    with open(ModelPath.MODEL_CACHE_PATH, 'rb') as f:
        return pickle.load(f)

async def get_personalized_recommendations(db: asyncpg.Connection, user_id: int, num_recommendations: int = 10) -> List[Dict]:
    """
    Generates personalized recommendations for a given user.
    """
    model_data = load_model_from_cache()
    if not model_data:
        print("Model not found. Please train the model first.")
        return []

    item_similarity = model_data['item_similarity']
    product_ids = model_data['product_ids']
    product_id_to_idx = model_data['product_id_to_idx']

    # Get products purchased by the user
    user_orders = await order_crud.get_orders_by_user(db, user_id)
    if not user_orders:
        return []

    purchased_product_ids = set()
    for order in user_orders:
        order_details = await order_crud.get_order_by_code(db, order['order_code'])
        if order_details and order_details.items:
            for item in order_details.items:
                purchased_product_ids.add(item.product_id)

    if not purchased_product_ids:
        return []

    # Calculate recommendation scores
    scores = {pid: 0.0 for pid in product_ids}
    
    for purchased_pid in purchased_product_ids:
        if purchased_pid not in product_id_to_idx:
            continue # This product was not in the training set
        
        purchased_idx = product_id_to_idx[purchased_pid]
        # Get similarity scores for this item with all other items
        similarity_scores = item_similarity[purchased_idx]

        for i, score in enumerate(similarity_scores):
            # Add the score to the item if it's not one the user already bought
            candidate_pid = product_ids[i]
            if candidate_pid not in purchased_product_ids:
                scores[candidate_pid] += score

    # Sort and get top N recommendations
    sorted_recommendations = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    
    recommended_ids = [pid for pid, score in sorted_recommendations if score > 0][:num_recommendations]

    # Fetch product details for the recommended IDs
    recommended_products = []
    for pid in recommended_ids:
        product = await product_crud.get_product_by_id(db, product_id=pid)
        if product:
            recommended_products.append(product.model_dump())
            
    return recommended_products
