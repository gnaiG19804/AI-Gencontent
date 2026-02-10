"""
Upload and Data Routes
- POST /upload - Upload CSV file
- GET /data - View uploaded data
"""
from fastapi import APIRouter, UploadFile, File, HTTPException

from services.file_analyzer import analyze_csv
from core.state import uploaded_data

router = APIRouter(tags=["Upload"])


@router.post("/upload")
async def upload_and_analyze(file: UploadFile = File(...)):
    """
    Upload file CSV và tự động phân tích cấu trúc
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file CSV")
    
    content = await file.read()
    result = analyze_csv(content)
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    
    uploaded_data["content"] = content
    uploaded_data["products"] = result["products"]
    uploaded_data["columns"] = result["column_names"]
    
    return {
        "status": "success",
        "file_name": file.filename,
        "total_rows": result["total_rows"],
        "total_columns": result["total_columns"],
        "columns": result["column_names"],  # Return simple strings for frontend
        "columns_metadata": result["columns"], # Keep metadata if needed
        "products": result["products"],
        "data_preview": result["products"][:5]
    }


@router.get("/data")
async def get_uploaded_data():
    """Xem toàn bộ data đã upload"""
    if "products" not in uploaded_data:
        raise HTTPException(status_code=400, detail="Chưa upload file nào")
    
    return {
        "columns": uploaded_data["columns"],
        "total_products": len(uploaded_data["products"]),
        "products": uploaded_data["products"]
    }
