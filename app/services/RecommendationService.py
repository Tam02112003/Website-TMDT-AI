from typing import List
from schemas import schemas
import re

def get_recommendations(target_product: schemas.Product, all_products: List[schemas.Product], num_recommendations: int = 5) -> List[schemas.Product]:
    """
    Recommends products based on keyword matching in name and description.
    """
    if not target_product:
        return []

    # Extract keywords from the target product's name and description
    target_text = f"{target_product.name} {target_product.description or ''}".lower()
    target_keywords = set(re.findall(r'\w+', target_text))

    if not target_keywords:
        return []

    recommendations = []
    for product in all_products:
        # Skip the target product itself
        if product.id == target_product.id:
            continue

        # Extract keywords from the current product
        product_text = f"{product.name} {product.description or ''}".lower()
        product_keywords = set(re.findall(r'\w+', product_text))

        # Calculate similarity score based on common keywords
        common_keywords = target_keywords.intersection(product_keywords)
        score = len(common_keywords)

        if score > 0:
            recommendations.append((product, score))

    # Sort recommendations by score in descending order
    recommendations.sort(key=lambda x: x[1], reverse=True)

    # Return the top N recommended products
    return [product for product, score in recommendations[:num_recommendations]]
