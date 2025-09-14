import pandas as pd
import asyncpg
import httpx
import json
import io
import math
from fastapi import UploadFile
from pydantic import ValidationError
from core.settings import settings
from core.app_config import logger
from schemas import schemas
from crud import product as product_crud

def sanitize_record(record: dict) -> dict:
    """Replace NaN/Infinity values with safe defaults before JSON serialization or DB insert."""
    clean_record = {}
    for key, value in record.items():
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            if key == "price":
                clean_record[key] = 0.0
            elif key == "quantity":
                clean_record[key] = 0
            else:
                clean_record[key] = None
        else:
            clean_record[key] = value
    return clean_record

async def process_csv_and_save(file: UploadFile, db: asyncpg.Connection):
    """
    Reads a CSV file, validates raw data, sends valid records to LLM for cleaning,
    validates again, and saves to the DB.
    Returns a detailed report of all successful and failed imports.
    """
    try:
        content = await file.read()
        try:
            df = pd.read_csv(io.BytesIO(content))
        except pd.errors.ParserError as e:
            logger.error(f"Failed to parse CSV file {file.filename}: {e}")
            raise ValueError(f"The uploaded file '{file.filename}' is not a valid CSV or is malformed.")

        raw_records = df.to_dict(orient='records')
        logger.info(f"Processing {len(raw_records)} records from CSV file: {file.filename}")

        # ---------------------------
        # STEP 1: Pre-validation (CSV level)
        # ---------------------------
        valid_rows = []
        raw_failed_records = []

        for row in raw_records:
            errors = []

            if not row.get("name") or str(row.get("name")).strip() == "":
                errors.append("Missing 'name'")

            try:
                if row.get("price") not in (None, "", " "):
                    float(row["price"])
            except Exception:
                errors.append("Invalid 'price' (must be a number)")

            try:
                if row.get("quantity") not in (None, "", " "):
                    int(float(row["quantity"]))  # float trước để xử lý 1.0
            except Exception:
                errors.append("Invalid 'quantity' (must be an integer)")

            if errors:
                sanitized_row = sanitize_record(row)
                raw_failed_records.append({"record": sanitized_row, "errors": errors})
            else:
                valid_rows.append(row)

        logger.info(f"Pre-validation result: {len(valid_rows)} valid, {len(raw_failed_records)} invalid from CSV")

        if not valid_rows:
            return {
                "message": "No valid records found in CSV file.",
                "successful_imports": 0,
                "raw_failed_imports": len(raw_failed_records),
                "llm_failed_imports": 0,
                "errors": raw_failed_records,
            }

        # 🔥 sanitize trước khi gửi sang LLM
        valid_rows = [sanitize_record(row) for row in valid_rows]

        # ---------------------------
        # STEP 2: Send valid rows to LLM
        # ---------------------------
        async with httpx.AsyncClient(timeout=None) as client:
            system_message = {
                "role": "system",
                "content": (
                    "Bạn là một chuyên gia xử lý dữ liệu. "
                    "Nhiệm vụ của bạn là làm sạch và chuẩn hóa mảng JSON các sản phẩm."
                    "QUY TẮC QUAN TRỌNG:"
                    "1. Mỗi sản phẩm PHẢI có 'name' (str), 'price' (float), và 'quantity' (int)."
                    "2. 'description' (Text) nếu thiếu thì tự sinh mô tả ngắn gọn."
                    "3. 'image_url' (str) nếu thiếu thì để null."
                    "4. Cắt bỏ khoảng trắng thừa ở các trường văn bản."
                    "5. Nếu thiếu 'quantity' thì mặc định là 0."
                    "6. Không bao giờ được trả về NaN, Infinity hoặc -Infinity."
                    "ĐẦU RA: Chỉ trả về JSON object có key 'products', giá trị là một mảng sản phẩm hợp lệ."
                )
            }
            user_message = {
                "role": "user",
                "content": json.dumps(valid_rows, indent=2, ensure_ascii=False)
            }

            llm_payload = {
                "model": settings.LOCAL_LLM.MODEL,
                "messages": [system_message, user_message],
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            }

            response = await client.post(settings.LOCAL_LLM.API_URL, json=llm_payload)
            response.raise_for_status()

            llm_response_content = response.json()["choices"][0]["message"]["content"].strip()

            try:
                json_objects = json.loads(llm_response_content)
                processed_data = json_objects.get("products", [])
                if not isinstance(processed_data, list):
                    raise ValueError("LLM did not return a list of products under 'products' key.")
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Error parsing LLM response: {e}")
                logger.debug(f"Raw LLM response: {llm_response_content}")
                raise ValueError("Could not extract valid products list from LLM response.")

        # ---------------------------
        # STEP 3: Validate with Pydantic and save
        # ---------------------------
        created_products = []
        llm_failed_records = []

        for record in processed_data:
            try:
                # sanitize lần nữa (phòng LLM vẫn trả về NaN/Infinity)
                record = sanitize_record(record)

                product_data = schemas.ProductCreate(**record)
                created_product = await product_crud.create_product(db=db, product=product_data)
                created_products.append(created_product)

            except ValidationError as e:
                logger.warning(f"Validation failed after LLM for record: {record}. Error: {e.errors()}")
                llm_failed_records.append({"record": record, "errors": e.errors()})
            except Exception as e:
                logger.error(f"Unexpected error saving record {record}: {e}")
                llm_failed_records.append({"record": record, "errors": [{"msg": str(e)}]})

        # ---------------------------
        # Summary
        # ---------------------------
        logger.info(
            f"CSV Processing Summary: {len(created_products)} successful, "
            f"{len(raw_failed_records)} raw failed, {len(llm_failed_records)} LLM failed."
        )

        return {
            "message": "CSV processing complete.",
            "successful_imports": len(created_products),
            "raw_failed_imports": len(raw_failed_records),
            "llm_failed_imports": len(llm_failed_records),
            "errors": {
                "raw_failed_records": raw_failed_records,
                "llm_failed_records": llm_failed_records,
            },
        }

    except Exception as e:
        logger.error(f"An error occurred during CSV processing: {e}", exc_info=True)
        raise