import pandas as pd
import io
from typing import Dict, Any, List


def analyze_csv(content: bytes) -> Dict[str, Any]:
    """
    Parse CSV và tự động phân tích cấu trúc file
    """
    try:
        file_stream = io.BytesIO(content)
        df = pd.read_csv(file_stream, on_bad_lines='warn')
        
        # Standardize column names
        df.columns = df.columns.str.strip()  # Remove whitespace
        
        # Custom mapping based on User Requirement
        # Target: Product_name, Vintage, cost_per_item (Luc), supplier
        column_mapping = {
            'Luc': 'cost_per_item',
            'luc': 'cost_per_item',
            'LUC': 'cost_per_item',
            'Supplier': 'supplier',
            'SUPPLIER': 'supplier',
            'Product Name': 'Product_name',
            'product_name': 'Product_name'
        }
        
        df.rename(columns=column_mapping, inplace=True)
        
        # Ensure required columns exist
        required_columns = ['Product_name', 'Vintage', 'cost_per_item', 'supplier']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
             return {
                "status": "error",
                "message": f"File CSV thiếu các cột bắt buộc: {', '.join(missing_columns)}. (Yêu cầu: Product_name, Vintage, Luc, supplier)"
            }
        
        columns_info = []
        total_missing = 0
        
        for col in df.columns:
            col_data = df[col]
            
            
            dtype = str(col_data.dtype)
            
            
            non_null_count = int(col_data.notna().sum())
            null_count = int(col_data.isna().sum())
            unique_count = int(col_data.nunique())
            total_missing += null_count
            
            sample_values = []
            for val in col_data.dropna().unique()[:3]:
                if isinstance(val, (int, float)):
                    sample_values.append(val if pd.notna(val) else None)
                else:
                    sample_values.append(str(val))
            
            columns_info.append({
                "name": col,
                "dtype": dtype,
                "non_null_count": non_null_count,
                "null_count": null_count,
                "unique_values": unique_count,
                "sample_values": sample_values,
                "has_missing": null_count > 0
            })
        
        
        products = df.replace({pd.NA: None, float('nan'): None, float('inf'): None, float('-inf'): None}).to_dict(orient="records")
        
        
        clean_products = []
        for product in products:
            clean_product = {}
            for key, value in product.items():
                if pd.isna(value):
                    clean_product[key] = None
                else:
                    clean_product[key] = value
            clean_products.append(clean_product)
        
        return {
            "status": "success",
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "total_missing_values": total_missing,
            "has_missing_data": total_missing > 0,
            "columns": columns_info,
            "column_names": df.columns.tolist(),
            "products": clean_products
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

