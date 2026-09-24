import json
import os
from fastapi import FastAPI, HTTPException
from typing import Dict, Any

app = FastAPI(title="Mock ERP System")

# Load data
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_json_file(filename: str) -> list:
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

@app.get("/vendor/{vendor_id}")
def get_vendor(vendor_id: str) -> Dict[str, Any]:
    vendors = load_json_file("vendors.json")
    for vendor in vendors:
        if vendor.get("vendor_id") == vendor_id:
            return vendor
    raise HTTPException(status_code=404, detail="Vendor not found")

@app.get("/po/{po_number}")
def get_purchase_order(po_number: str) -> Dict[str, Any]:
    pos = load_json_file("purchase_orders.json")
    for po in pos:
        if po.get("po_number") == po_number:
            return po
    raise HTTPException(status_code=404, detail="Purchase Order not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
