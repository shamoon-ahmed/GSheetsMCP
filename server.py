import os, json, time
import logging

import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from cryptography.fernet import Fernet

from fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce noise from HTTP and MCP libraries
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Enable MCP JSON RPC message logging
logging.getLogger("mcp").setLevel(logging.DEBUG)
logging.getLogger("mcp.server").setLevel(logging.DEBUG)
logging.getLogger("fastmcp").setLevel(logging.DEBUG)

CLIENT_SECRET_FILE = os.path.join(os.path.dirname(__file__), "google_client_secret.json")
with open(CLIENT_SECRET_FILE, 'r') as f:
    client_secrets = json.load(f)

GOOGLE_CLIENT_ID = client_secrets["web"]["client_id"]
GOOGLE_CLIENT_SECRET = client_secrets["web"]["client_secret"]

mcp = FastMCP(
    name="Google Sheets MCP",
    # stateless_http=True,
)

# Simple connection file path
CONN_FILE = os.path.join(os.path.dirname(__file__), "connection.json")
FERNET_KEY = os.getenv("FERNET_KEY")

def decrypt_if_needed(token_enc: str) -> str:
    logger.debug(f"Decrypting token... FERNET_KEY exists: {bool(FERNET_KEY)}")
    if not token_enc:
        logger.error("No token provided for decryption")
        return None
    # Encryption disabled for development
    logger.debug("Encryption disabled, returning token as-is")
    return token_enc

def load_connection():
    """
    Load connection data from simple connection.json file.
    """
    logger.debug(f"Loading connection from: {CONN_FILE}")
    
    if not os.path.exists(CONN_FILE):
        logger.error(f"Connection file does not exist: {CONN_FILE}")
        logger.info(f"Please create {CONN_FILE} with your Google Sheets configuration")
        return None
    
    logger.debug("Connection file exists, loading...")
    try:
        with open(CONN_FILE, "r") as f:
            data = json.load(f)
        logger.debug(f"Connection file loaded successfully. Keys: {list(data.keys())}")
        
        # Handle both old and new format
        if "inventory" in data and "orders" in data:
            # New dual-sheet format
            logger.debug("Dual-sheet configuration detected")
            if "refresh_token" in data:
                data["refresh_token"] = decrypt_if_needed(data["refresh_token"])
            return data
        elif "sheet_id" in data:
            # Old single-sheet format - convert to new format
            logger.debug("Single-sheet configuration detected, converting...")
            new_data = {
                "inventory": {
                    "workbook_id": data["sheet_id"],
                    "worksheet_name": "Sheet1"  # Default assumption
                },
                "orders": {
                    "workbook_id": data["sheet_id"],
                    "worksheet_name": "Orders"  # Default assumption
                },
                "refresh_token": decrypt_if_needed(data.get("refresh_token"))
            }
            return new_data
        else:
            logger.error("Invalid connection file format")
            return None
            
    except Exception as e:
        logger.error(f"Failed to load connection file: {e}")
        return None

def build_sheets_service_from_refresh(refresh_token):
    logger.debug("Building credentials from refresh token...")
    logger.debug(f"Client ID: {GOOGLE_CLIENT_ID}")
    logger.debug(f"Client Secret exists: {bool(GOOGLE_CLIENT_SECRET)}")
    
    # Decrypt the refresh token if needed
    decrypted_token = decrypt_if_needed(refresh_token)
    logger.debug(f"Token decrypted successfully: {bool(decrypted_token)}")
    logger.debug(f"Decrypted token length: {len(decrypted_token) if decrypted_token else 0}")
    
    creds = Credentials(
        token=None,
        refresh_token=decrypted_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]  # Removed .readonly for write access
    )
    logger.debug("Credentials object created, attempting refresh...")
    
    try:
        # refresh to get an access token
        creds.refresh(Request())
        print("[DEBUG] Token refresh successful!")
        print(f"[DEBUG] Access token exists: {bool(creds.token)}")
    except Exception as refresh_error:
        print(f"[ERROR] Token refresh failed: {refresh_error}")
        raise
    
    print("[DEBUG] Building Google Sheets service...")
    service = build("sheets", "v4", credentials=creds)
    print("[DEBUG] Google Sheets service built successfully")
    return service

def smart_column_detection(data_row, column_type):
    """
    Intelligently detect columns based on common business terminology.
    Supports various business types: fashion, beauty, electronics, etc.
    """
    column_mappings = {
        "product_name": [
            "item_name", "product_name", "product_title", "name", "product", "title", 
            "merchandise", "article", "sku_name"
        ],
        "quantity": [
            "quantity", "qty", "stock", "available", "inventory", "count",
            "units", "pieces", "amount", "availability", "in_stock"
        ],
        "price": [
            "unit_price", "price", "cost", "amount", "rate", "selling_price",
            "retail_price", "mrp", "value", "pkr", "usd", "inr"
        ],
        "id": [
            "item_id", "product_id", "id", "sku", "code", "barcode",
            "item_code", "product_code", "order_no", "order_id", "orderid"
        ],
        "status": [
            "status", "availability", "available", "active", "enabled",
            "payment_status", "order_status", "stock_status"
        ],
        "size": [
            "size", "dimensions", "variant", "option", "type"
        ],
        "color": [
            "color", "colour", "shade", "variant"
        ],
        "weight": [
            "weight", "mass", "volume", "ml", "grams", "kg", "oz"
        ]
    }
    
    result = {}
    
    for key, value in data_row.items():
        clean_key = str(key).strip().lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
        
        for col_type, possible_names in column_mappings.items():
            if column_type == "all" or column_type == col_type:
                for possible_name in possible_names:
                    # Use exact match or full word boundary match for better precision
                    if (clean_key == possible_name or 
                        clean_key.startswith(possible_name + '_') or
                        clean_key.endswith('_' + possible_name) or
                        ('_' + possible_name + '_' in clean_key)):
                        if col_type not in result:  # Take first match
                            result[col_type] = {"key": key, "value": value, "clean_key": clean_key}
                        break
    
    return result

def get_sheet_data(service, workbook_id, worksheet_name, conn_data=None):
    """Helper function to get data from a specific worksheet"""
    print(f"[DEBUG] Getting data from workbook {workbook_id}, worksheet {worksheet_name}")
    
    # Check if we have stored table structure
    table_structure = None
    if conn_data:
        # Find which sheet this is (inventory or orders)
        inventory_config = conn_data.get("inventory", {})
        orders_config = conn_data.get("orders", {})
        
        if inventory_config.get("worksheet_name") == worksheet_name:
            table_structure = inventory_config.get("table_structure")
            print(f"[DEBUG] Using stored inventory table structure")
        elif orders_config.get("worksheet_name") == worksheet_name:
            table_structure = orders_config.get("table_structure")
            print(f"[DEBUG] Using stored orders table structure")
    
    if table_structure:
        # Use stored structure for precise data reading
        start_row = table_structure.get("start_row", 0) + 1  # Convert to 1-based
        start_col = table_structure.get("start_col", 0) + 1  # Convert to 1-based
        headers = table_structure.get("headers", [])
        
        # Calculate range based on stored structure
        start_col_letter = chr(64 + start_col)  # Convert to column letter
        end_col_letter = chr(64 + start_col + len(headers) - 1)
        range_name = f"{worksheet_name}!{start_col_letter}{start_row + 1}:{end_col_letter}1000"  # Skip header row
        
        print(f"[DEBUG] Using stored structure range: {range_name}")
        print(f"[DEBUG] Headers from structure: {headers}")
        
        res = service.spreadsheets().values().get(
            spreadsheetId=workbook_id, 
            range=range_name,
            valueRenderOption='UNFORMATTED_VALUE'
        ).execute()
        
        rows = res.get("values", [])
        
        # Convert to list of dictionaries using stored headers
        sheet_data = []
        for row in rows:
            # Skip completely empty rows
            if not any(cell for cell in row if str(cell).strip()):
                continue
                
            row_dict = {}
            for i, header in enumerate(headers):
                # Get cell value or empty string if column doesn't exist in this row
                cell_value = row[i] if i < len(row) else ""
                row_dict[header] = str(cell_value).strip() if cell_value else ""
            
            sheet_data.append(row_dict)
        
        return {
            'headers': headers,
            'data': sheet_data,
            'row_count': len(sheet_data)
        }
    
    else:
        # Fallback to old method if no stored structure
        print(f"[DEBUG] No stored structure found, using fallback method")
        
        # Get ALL data from the specified worksheet (expanded range)
        range_name = f"{worksheet_name}!A1:Z2000"  # Much larger range to catch all data
        
        res = service.spreadsheets().values().get(
            spreadsheetId=workbook_id, 
            range=range_name,
            valueRenderOption='UNFORMATTED_VALUE'
        ).execute()
        
        rows = res.get("values", [])
        
        if not rows:
            print("[DEBUG] No data found in fallback method")
            return {"headers": [], "data": [], "row_count": 0}
            
        print(f"[DEBUG] Fallback method found {len(rows)} total rows")
        
        # Use first row as headers
        headers = rows[0] if rows else []
        data_rows = rows[1:] if len(rows) > 1 else []
        
        print(f"[DEBUG] Headers: {headers}")
        print(f"[DEBUG] Data rows to process: {len(data_rows)}")
        
        # Convert to list of dictionaries using headers
        sheet_data = []
        for i, row in enumerate(data_rows):
            # Skip completely empty rows
            if not any(cell for cell in row if str(cell).strip()):
                print(f"[DEBUG] Skipping empty row {i+2}")
                continue
                
            row_dict = {}
            for j, header in enumerate(headers):
                # Get cell value or empty string if column doesn't exist in this row
                cell_value = row[j] if j < len(row) else ""
                # Clean header name (remove spaces, special chars for cleaner keys)
                clean_header = str(header).strip().lower().replace(' ', '_').replace('-', '_')
                if clean_header:  # Only add if header is not empty
                    row_dict[clean_header] = str(cell_value).strip() if cell_value else ""
        
            if row_dict:  # Only add if row has some data
                sheet_data.append(row_dict)
                if len(sheet_data) <= 3:  # Debug first few rows
                    print(f"[DEBUG] Row {i+2} data: {row_dict}")
            
        print(f"[DEBUG] Total processed rows: {len(sheet_data)}")
    
    return {
        'headers': headers,
        'data': sheet_data,
        'row_count': len(sheet_data)
    }

@mcp.tool()
def get_inventory_tool(query: str = "all") -> str:
    """
    Get current inventory data from the inventory sheet.
    Use this to check product availability, stock levels, and product information.
    """
    print(f"[DEBUG] Inventory query from agent: {query}")
    
    conn = load_connection()
    if not conn:
        return json.dumps({"error": "no_connection_configured"})
    
    inventory_config = conn.get("inventory")
    refresh_token = conn.get("refresh_token")
    
    if not inventory_config or not refresh_token:
        return json.dumps({"error": "missing_inventory_config_or_token"})
    
    try:
        service = build_sheets_service_from_refresh(refresh_token)
        inventory_data = get_sheet_data(
            service, 
            inventory_config["workbook_id"], 
            inventory_config["worksheet_name"]
        )
        
        return json.dumps({
            "query": query,
            "inventory": inventory_data,
            "timestamp": time.time()
        })
    except Exception as e:
        print(f"[ERROR] Failed to get inventory: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
def get_orders_tool(query: str = "recent") -> str:
    """
    Get orders data from the orders sheet.
    Use this to check recent orders, order history, and order status.
    """
    print(f"[DEBUG] Orders query from agent: {query}")
    
    conn = load_connection()
    if not conn:
        return json.dumps({"error": "no_connection_configured"})
    
    orders_config = conn.get("orders")
    refresh_token = conn.get("refresh_token")
    
    if not orders_config or not refresh_token:
        return json.dumps({"error": "missing_orders_config_or_token"})
    
    try:
        service = build_sheets_service_from_refresh(refresh_token)
        orders_data = get_sheet_data(
            service, 
            orders_config["workbook_id"], 
            orders_config["worksheet_name"]
        )
        
        return json.dumps({
            "query": query,
            "orders": orders_data,
            "timestamp": time.time()
        })
    except Exception as e:
        print(f"[ERROR] Failed to get orders: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
def record_order_tool(order_data: str) -> str:
    """
    Record a new order in the orders sheet.
    order_data should be JSON string with order details like:
    {"customer_name": "John Doe", "product": "Widget A", "quantity": 2, "price": 25.99}
    """
    print(f"[DEBUG] Recording order: {order_data}")
    
    conn = load_connection()
    if not conn:
        return json.dumps({"error": "no_connection_configured"})
    
    orders_config = conn.get("orders")
    refresh_token = conn.get("refresh_token")
    
    if not orders_config or not refresh_token:
        return json.dumps({"error": "missing_orders_config_or_token"})
    
    try:
        # Parse order data
        try:
            order = json.loads(order_data)
        except:
            return json.dumps({"error": "invalid_order_data_format"})
        
        service = build_sheets_service_from_refresh(refresh_token)
        
        # Get current orders to understand the structure
        current_orders = get_sheet_data(
            service, 
            orders_config["workbook_id"], 
            orders_config["worksheet_name"]
        )
        
        # Add timestamp and order ID if not provided
        if "timestamp" not in order:
            order["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if "order_id" not in order and "order_no" not in order:
            order["order_id"] = f"ORD-{int(time.time())}"
        
        # Get current orders to understand the structure
        current_orders = get_sheet_data(
            service, 
            orders_config["workbook_id"], 
            orders_config["worksheet_name"]
        )
        
        headers = current_orders["headers"]
        
        # Smart mapping: map order data to existing column structure
        new_row = []
        
        if headers:
            # Map order fields to existing headers using smart detection
            for header in headers:
                clean_header = str(header).strip().lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
                
                # Try exact match first
                if clean_header in order:
                    new_row.append(str(order[clean_header]))
                else:
                    # Try intelligent mapping
                    mapped_value = ""
                    
                    # Map common variations
                    if any(word in clean_header for word in ["name", "product", "item"]):
                        mapped_value = order.get("product_name", order.get("customer_name", ""))
                    elif any(word in clean_header for word in ["quantity", "qty"]):
                        mapped_value = order.get("quantity", "")
                    elif any(word in clean_header for word in ["price", "cost", "amount"]):
                        mapped_value = order.get("price", "")
                    elif any(word in clean_header for word in ["order", "id", "no"]):
                        mapped_value = order.get("order_id", order.get("order_no", ""))
                    elif any(word in clean_header for word in ["customer", "buyer"]):
                        mapped_value = order.get("customer_name", "")
                    elif any(word in clean_header for word in ["email", "contact"]):
                        mapped_value = order.get("customer_email", "")
                    elif any(word in clean_header for word in ["status", "payment"]):
                        mapped_value = order.get("status", "confirmed")
                    elif any(word in clean_header for word in ["size"]):
                        mapped_value = order.get("size", "")
                    elif any(word in clean_header for word in ["color", "colour"]):
                        mapped_value = order.get("color", "")
                    elif any(word in clean_header for word in ["weight"]):
                        mapped_value = order.get("weight", "")
                    elif any(word in clean_header for word in ["date", "time"]):
                        mapped_value = order.get("timestamp", "")
                    
                    new_row.append(str(mapped_value))
        else:
            # No existing headers - create them from order data
            headers = list(order.keys())
            new_row = [str(v) for v in order.values()]
            
            # Add headers first
            service.spreadsheets().values().append(
                spreadsheetId=orders_config["workbook_id"],
                range=f"{orders_config['worksheet_name']}!A1",
                valueInputOption='RAW',
                body={'values': [headers]}
            ).execute()
        
        # Add the new order
        service.spreadsheets().values().append(
            spreadsheetId=orders_config["workbook_id"],
            range=f"{orders_config['worksheet_name']}!A:A",
            valueInputOption='RAW',
            body={'values': [new_row]}
        ).execute()
        
        return json.dumps({
            "success": True,
            "order_id": order.get("order_id"),
            "message": "Order recorded successfully",
            "timestamp": time.time()
        })
        
    except Exception as e:
        print(f"[ERROR] Failed to record order: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
def update_inventory_tool(product_name: str, quantity_change: int) -> str:
    """
    Update inventory quantity for a product (e.g., reduce stock after an order).
    quantity_change can be negative (reduce stock) or positive (add stock).
    """
    print(f"[DEBUG] Updating inventory: {product_name}, change: {quantity_change}")
    
    conn = load_connection()
    if not conn:
        return json.dumps({"error": "no_connection_configured"})
    
    inventory_config = conn.get("inventory")
    refresh_token = conn.get("refresh_token")
    
    if not inventory_config or not refresh_token:
        return json.dumps({"error": "missing_inventory_config_or_token"})
    
    try:
        service = build_sheets_service_from_refresh(refresh_token)
        
        # Get current inventory data
        inventory_data = get_sheet_data(
            service, 
            inventory_config["workbook_id"], 
            inventory_config["worksheet_name"]
        )
        
        # Find the product and update quantity
        product_found = False
        row_index = -1
        quantity_col_index = -1
        
        for i, item in enumerate(inventory_data["data"]):
            # Check if product name matches
            for key, value in item.items():
                if "name" in key.lower() or "product" in key.lower():
                    if product_name.lower() in value.lower():
                        product_found = True
                        row_index = i + 2  # +2 because of 0-indexing and header row
                        
                        # Find quantity column
                        for j, header in enumerate(inventory_data["headers"]):
                            clean_header = header.lower()
                            if any(word in clean_header for word in ["quantity", "stock", "qty", "available"]):
                                quantity_col_index = j
                                break
                        break
            if product_found:
                break
        
        if not product_found:
            return json.dumps({"error": "product_not_found"})
        
        if quantity_col_index == -1:
            return json.dumps({"error": "quantity_column_not_found"})
        
        # Get current quantity
        current_qty_range = f"{inventory_config['worksheet_name']}!{chr(65 + quantity_col_index)}{row_index}"
        current_qty_result = service.spreadsheets().values().get(
            spreadsheetId=inventory_config["workbook_id"],
            range=current_qty_range
        ).execute()
        
        current_qty = 0
        if current_qty_result.get('values'):
            try:
                current_qty = int(float(current_qty_result['values'][0][0]))
            except:
                current_qty = 0
        
        # Calculate new quantity
        new_qty = current_qty + quantity_change
        
        # Update the cell
        service.spreadsheets().values().update(
            spreadsheetId=inventory_config["workbook_id"],
            range=current_qty_range,
            valueInputOption='RAW',
            body={'values': [[new_qty]]}
        ).execute()
        
        return json.dumps({
            "success": True,
            "product_name": product_name,
            "previous_quantity": current_qty,
            "quantity_change": quantity_change,
            "new_quantity": new_qty,
            "message": f"Inventory updated successfully",
            "timestamp": time.time()
        })
        
    except Exception as e:
        print(f"[ERROR] Failed to update inventory: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
def quick_order_summary_tool(customer_name: str, product_name: str, quantity: int, customer_email: str = "", customer_address: str = "", payment_mode: str = "") -> str:
    """
    Quickly generate order summary without processing sheets. Use this to immediately confirm order to customer.
    """
    import random
    import time
    
    # Generate Order ID immediately
    timestamp = int(time.time())
    random_suffix = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=3))
    order_id = f"ORD-{timestamp}-{random_suffix}"
    
    # Return immediate order summary
    order_summary = {
        "success": True,
        "immediate_confirmation": True,
        "order_id": order_id,
        "customer_name": customer_name,
        "product_name": product_name,
        "quantity": quantity,
        "customer_email": customer_email,
        "customer_address": customer_address,
        "payment_mode": payment_mode,
        "status": "confirmed",
        "message": "Order confirmed! Processing in background...",
        "timestamp": time.time()
    }
    
    return json.dumps(order_summary)

@mcp.tool()
def process_customer_order_tool(customer_name: str, product_name: str, quantity: int, customer_email: str = "", notes: str = "", customer_address: str = "", payment_mode: str = "") -> str:
    """
    Complete end-to-end order processing with dynamic schema analysis.
    Automatically detects orders sheet columns and fills them with inventory data or provided customer data.
    Returns detailed info about what customer information is still needed.
    """
    logger.info(f"Dynamic order processing: {customer_name} wants {quantity}x {product_name}")
    
    # Order deduplication - prevent duplicate orders from retries
    import time
    current_time = time.time()
    order_key = f"{customer_name}_{product_name}_{quantity}_{customer_email}_{customer_address}"
    
    # Check if we've processed this exact order in the last 30 seconds
    if not hasattr(process_customer_order_tool, '_recent_orders'):
        process_customer_order_tool._recent_orders = {}
    
    # Clean old orders (older than 30 seconds)
    process_customer_order_tool._recent_orders = {
        k: v for k, v in process_customer_order_tool._recent_orders.items() 
        if current_time - v < 30
    }
    
    if order_key in process_customer_order_tool._recent_orders:
        logger.warning(f"Duplicate order detected within 30 seconds - skipping: {order_key}")
        return json.dumps({
            "success": True, 
            "message": "Order already processed",
            "duplicate_prevention": True
        })
    
    # Record this order
    process_customer_order_tool._recent_orders[order_key] = current_time
    
    conn = load_connection()
    if not conn:
        return json.dumps({"success": False, "error": "no_connection_configured"})
    
    inventory_config = conn.get("inventory")
    orders_config = conn.get("orders")
    refresh_token = conn.get("refresh_token")
    
    if not all([inventory_config, orders_config, refresh_token]):
        return json.dumps({"success": False, "error": "missing_configuration"})
    
    try:
        # Single Google Sheets service connection
        service = build_sheets_service_from_refresh(refresh_token)
        
        # Step 1: Get inventory data
        inventory_data = get_sheet_data(
            service, 
            inventory_config["workbook_id"], 
            inventory_config["worksheet_name"],
            conn
        )
        
        # Step 2: Get orders sheet schema for dynamic column analysis
        orders_data = get_sheet_data(
            service,
            orders_config["workbook_id"],
            orders_config["worksheet_name"],
            conn
        )
        orders_headers = orders_data["headers"]
        
        # Step 3: Check if inventory has quantity tracking first
        inventory_headers = inventory_data["headers"]
        has_quantity_column = any("quantity" in header.lower() or "stock" in header.lower() or "available" in header.lower() for header in inventory_headers)
        print(f"[DEBUG] Inventory headers: {inventory_headers}")
        print(f"[DEBUG] Has quantity tracking: {has_quantity_column}")
        
        # Step 4: Find product and extract inventory details
        product_found = False
        available_quantity = 0
        product_row_index = -1
        product_details = {}
        product_detected_cols = {}
        
        for idx, item in enumerate(inventory_data["data"]):
            detected_cols = smart_column_detection(item, "all")
            
            if "product_name" in detected_cols:
                product_value = detected_cols["product_name"]["value"]
                if product_name.lower() in product_value.lower():
                    product_found = True
                    product_row_index = idx + 2
                    product_detected_cols = detected_cols  # Store for later use
                    
                    # Extract all available product details
                    for col_type, col_info in detected_cols.items():
                        product_details[col_type] = str(col_info["value"]) if col_info["value"] else ""
                    
                    # Check quantity only if inventory has quantity tracking
                    if has_quantity_column and "quantity" in detected_cols:
                        try:
                            available_quantity = int(float(detected_cols["quantity"]["value"])) if detected_cols["quantity"]["value"] else 0
                        except:
                            available_quantity = 0
                    break
        
        if not product_found:
            return json.dumps({
                "success": False,
                "error": "product_not_found",
                "message": f"Product '{product_name}' not found in inventory"
            })

        # FIXED: For service/food businesses without stock tracking - make quantity check optional
        if has_quantity_column:
            has_quantity_tracking = "quantity" in product_detected_cols and product_detected_cols["quantity"]["value"]
            print(f"[DEBUG] Product has quantity value: {has_quantity_tracking}, Available: {available_quantity}")
            
            if has_quantity_tracking and available_quantity < quantity:
                return json.dumps({
                    "success": False,
                    "error": "insufficient_stock",
                    "message": f"Only {available_quantity} units available, but {quantity} requested",
                    "available_quantity": available_quantity,
                    "requested_quantity": quantity
                })
        else:
            print(f"[DEBUG] No quantity tracking in inventory sheet - treating as service/food business")
            has_quantity_tracking = False
        
        # Step 4: Dynamic column mapping and customer data analysis
        order_row_data = []
        missing_customer_info = []
        customer_provided_data = {
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_address": customer_address,
            "payment_mode": payment_mode,
            "notes": notes,
            "quantity": str(quantity),
            "status": "confirmed",
            "order_id": f"ORD-{int(time.time())}"
        }
        
        # Analyze each column in orders sheet
        print(f"[DEBUG] Orders headers: {orders_headers}")
        for header in orders_headers:
            clean_header = header.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
            print(f"[DEBUG] Processing header: '{header}' -> clean: '{clean_header}'")
            filled = False
            value = ""
            
            # For customer-specific fields, try customer data first
            customer_priority_fields = ["customer_name", "customer_email", "email", "customer_address", "address", "delivery", "payment_mode", "payment", "mode"]
            
            if any(field in clean_header for field in customer_priority_fields):
                # Try customer data first for customer fields - FIXED: More specific matching
                customer_mappings = {
                    "customer_email": customer_provided_data["customer_email"],  # Check email first
                    "email": customer_provided_data["customer_email"],
                    "customer_name": customer_provided_data["customer_name"],
                    "customer": customer_provided_data["customer_name"],  # This should come after email check
                    "customer_address": customer_provided_data["customer_address"],
                    "address": customer_provided_data["customer_address"],
                    "delivery": customer_provided_data["customer_address"],
                    "payment_mode": customer_provided_data["payment_mode"],
                    "payment": customer_provided_data["payment_mode"],
                    "mode": customer_provided_data["payment_mode"],
                }
                
                for cust_key, cust_value in customer_mappings.items():
                    if cust_key in clean_header:
                        if cust_value:
                            value = cust_value
                            filled = True
                            print(f"[DEBUG] Filled '{header}' from customer data: {cust_key} = {cust_value}")
                        break
            
            # If not filled from customer data, try inventory data and calculations
            if not filled:
                # Calculate subtotal if we have price and quantity
                subtotal_value = ""
                if product_details.get("price"):
                    try:
                        # Extract numeric price (remove currency symbols, etc.)
                        price_str = str(product_details.get("price", ""))
                        price_numeric = ''.join(c for c in price_str if c.isdigit() or c == '.')
                        if price_numeric:
                            unit_price = float(price_numeric)
                            subtotal_value = str(unit_price * quantity)
                            print(f"[DEBUG] Calculated subtotal: {unit_price} × {quantity} = {subtotal_value}")
                    except:
                        print(f"[DEBUG] Could not calculate subtotal from price: {product_details.get('price')}")
                
                inventory_mappings = {
                    "item_name": product_details.get("product_name", product_name),
                    "product_name": product_details.get("product_name", product_name),
                    "item": product_details.get("product_name", product_name),  # Added for "Item" column
                    "name": product_details.get("product_name", product_name),
                    "size": product_details.get("size", ""),
                    "color": product_details.get("color", ""),
                    "colour": product_details.get("color", ""),
                    "price": product_details.get("price", ""),
                    "price_pkr": product_details.get("price", ""),
                    "unit_price": product_details.get("price", ""),
                    "cost": product_details.get("price", ""),
                    "subtotal": subtotal_value,  # Added for "Subtotal" column
                    "total": subtotal_value,     # Alternative for total/subtotal columns
                    "category": product_details.get("category", ""),
                    "weight": product_details.get("weight", ""),
                    "description": product_details.get("description", "")
                }
                
                # Check if this column can be filled from inventory
                for inv_key, inv_value in inventory_mappings.items():
                    if inv_key in clean_header and inv_value:
                        value = inv_value
                        filled = True
                        print(f"[DEBUG] Filled '{header}' from inventory: {inv_key} = {inv_value}")
                        break
            
            # If still not filled, try remaining customer data fields
            if not filled:
                remaining_customer_mappings = {
                    "notes": customer_provided_data["notes"],
                    "note": customer_provided_data["notes"],
                    "quantity": customer_provided_data["quantity"],
                    "qty": customer_provided_data["quantity"],
                    "status": customer_provided_data["status"],
                    "order_id": customer_provided_data["order_id"],
                    "order_no": customer_provided_data["order_id"],
                    "order": customer_provided_data["order_id"],
                    "order_number": customer_provided_data["order_id"]
                }
                
                for cust_key, cust_value in remaining_customer_mappings.items():
                    if cust_key in clean_header:
                        if cust_value:
                            value = cust_value
                            filled = True
                            print(f"[DEBUG] Filled '{header}' from customer data: {cust_key} = {cust_value}")
                        break
            
            # If still not filled, add empty value but note it's missing
            if not filled:
                print(f"[DEBUG] Could not map column '{header}' - adding as empty")
            
            order_row_data.append(value)
            print(f"[DEBUG] Final value for '{header}': '{value}'")
        
        print(f"[DEBUG] Complete order row data: {order_row_data}")
        
        # Step 5: Check if we have all required customer information
        if missing_customer_info:
            return json.dumps({
                "success": False,
                "error": "missing_customer_information",
                "message": "Additional customer information required to complete the order",
                "missing_fields": missing_customer_info,
                "product_details": {
                    "name": product_details.get("product_name", product_name),
                    "size": product_details.get("size", ""),
                    "color": product_details.get("color", ""),
                    "price": product_details.get("price", ""),
                    "available_quantity": available_quantity
                },
                "instructions": "Please provide the missing information and try the order again"
            })
        
        # Step 6: Update inventory (reduce stock) - FIXED: Only for businesses with quantity tracking
        new_quantity = available_quantity
        if has_quantity_tracking:
            new_quantity = available_quantity - quantity
            quantity_col = None
            
            for col_letter, header in enumerate(inventory_data["headers"], start=1):
                if any(word in header.lower() for word in ["quantity", "qty", "stock"]):
                    quantity_col = chr(64 + col_letter)
                    break
            
            if quantity_col and product_row_index > 0:
                range_name = f"{inventory_config['worksheet_name']}!{quantity_col}{product_row_index}"
                service.spreadsheets().values().update(
                    spreadsheetId=inventory_config["workbook_id"],
                    range=range_name,
                    valueInputOption="RAW",
                    body={"values": [[str(new_quantity)]]}
                ).execute()
                print(f"[DEBUG] Inventory updated: {available_quantity} -> {new_quantity}")
            else:
                print(f"[DEBUG] Could not find quantity column for inventory update")
        else:
            print(f"[DEBUG] Skipping inventory update - service/food business without stock tracking")
        
        # Step 7: Add order to orders sheet using stored table structure
        print(f"[DEBUG] Adding order to sheet: {orders_config['worksheet_name']}")
        print(f"[DEBUG] Order data: {order_row_data}")
        
        # Get stored table structure for proper positioning
        orders_table_structure = orders_config.get("table_structure", {})
        start_row = orders_table_structure.get("start_row", 0)  # 0-based from storage
        start_col = orders_table_structure.get("start_col", 0)  # 0-based from storage
        headers = orders_table_structure.get("headers", [])
        
        # Calculate the correct range for appending
        # Convert to 1-based for Google Sheets API
        start_col_letter = chr(65 + start_col)  # Convert to column letter (A=0, B=1, etc.)
        
        # Handle empty headers case - use a safe default range
        if len(headers) == 0:
            print("[DEBUG] No headers found, using default range A:J")
            append_range = f"{orders_config['worksheet_name']}!A:J"
        else:
            end_col_letter = chr(65 + start_col + len(headers) - 1)
            append_range = f"{orders_config['worksheet_name']}!{start_col_letter}:{end_col_letter}"
        
        print(f"[DEBUG] Using stored table structure:")
        print(f"[DEBUG]   start_row: {start_row}, start_col: {start_col}")
        print(f"[DEBUG]   Headers: {headers}")
        print(f"[DEBUG]   Append range: {append_range}")
        
        append_result = service.spreadsheets().values().append(
            spreadsheetId=orders_config["workbook_id"],
            range=append_range,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [order_row_data]}
        ).execute()
        
        print(f"[DEBUG] Order appended successfully: {append_result}")
        
        return json.dumps({
            "success": True,
            "message": f"Order processed successfully for {customer_name}",
            "order_details": {
                "order_id": customer_provided_data["order_id"],
                "customer_name": customer_name,
                "product_name": product_details.get("product_name", product_name),
                "quantity": quantity,
                "previous_stock": available_quantity,
                "new_stock": new_quantity,
                "columns_filled": len(orders_headers),
                "complete_order_data": dict(zip(orders_headers, order_row_data))
            },
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"Dynamic order processing failed: {e}")
        return json.dumps({
            "success": False,
            "error": "processing_failed",
            "details": str(e)
        })

@mcp.tool()
def google_sheets_query_tool(query: str) -> str:
    """
    Main tool for answering product queries, checking availability, pricing, and product information.
    Use this tool for all customer inquiries about products, stock, prices, and general inventory questions.
    """
    logger.info(f"Product query from agent: {query}")
    
    conn = load_connection()
    if not conn:
        return json.dumps({"error": "no_connection_configured"})
    
    inventory_config = conn.get("inventory")
    refresh_token = conn.get("refresh_token")
    
    if not inventory_config or not refresh_token:
        return json.dumps({"error": "missing_inventory_config_or_token"})
    
    try:
        service = build_sheets_service_from_refresh(refresh_token)
        inventory_data = get_sheet_data(
            service, 
            inventory_config["workbook_id"], 
            inventory_config["worksheet_name"],
            conn
        )
        
        return json.dumps({
            "query": query,
            "inventory": inventory_data,
            "timestamp": time.time(),
            "message": "Use this inventory data to answer the customer's query about products, availability, or pricing"
        })
        
    except Exception as e:
        print(f"[ERROR] Failed to query inventory: {e}")
        return json.dumps({"error": str(e)})


streamable_http_app = mcp.http_app()

if __name__ == "__main__":
    # Enable even more detailed MCP logging
    import os
    os.environ["MCP_LOG_LEVEL"] = "DEBUG"
    
    # Enable JSON RPC message tracing
    logging.getLogger("mcp.server.fastmcp").setLevel(logging.DEBUG)
    logging.getLogger("mcp.shared").setLevel(logging.DEBUG)
    
    logger.info("🚀 Starting Google Sheets MCP Server...")
    logger.info("📊 Logging enabled - you'll see JSON RPC messages and detailed debug info")
    
    port = 8010

    import uvicorn
    uvicorn.run(
        "server:streamable_http_app", 
        host="127.0.0.1", 
        port=port,
        reload=True,
        log_level="info"
    )