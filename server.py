import os, json, time
import logging

import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from cryptography.fernet import Fernet

from fastmcp import FastMCP

from fastmcp.server.dependencies import get_http_headers

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
    stateless_http=True,
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
    exact_matches = {}
    
    # First pass: collect all exact matches (highest priority)
    for key, value in data_row.items():
        clean_key = str(key).strip().lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
        
        for col_type, possible_names in column_mappings.items():
            if column_type == "all" or column_type == col_type:
                for possible_name in possible_names:
                    # Exact match - highest priority
                    if clean_key == possible_name:
                        if col_type not in exact_matches:  # Take first exact match
                            exact_matches[col_type] = {"key": key, "value": value, "clean_key": clean_key}
                        break
    
    # Second pass: partial matches only if no exact match found
    for key, value in data_row.items():
        clean_key = str(key).strip().lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
        
        for col_type, possible_names in column_mappings.items():
            if column_type == "all" or column_type == col_type:
                # Skip if we already have an exact match for this column type
                if col_type in exact_matches:
                    continue
                    
                for possible_name in possible_names:
                    # Partial match patterns
                    if (clean_key.startswith(possible_name + '_') or
                        clean_key.endswith('_' + possible_name) or
                        ('_' + possible_name + '_' in clean_key)):
                        if col_type not in result:  # Take first partial match
                            result[col_type] = {"key": key, "value": value, "clean_key": clean_key}
                        break
    
    # Combine exact matches and partial matches
    result.update(exact_matches)
    
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
    
    logger.debug(f"Order key: {order_key}")
    
    # Check if we've processed this exact order in the last 30 seconds
    if not hasattr(process_customer_order_tool, '_recent_orders'):
        process_customer_order_tool._recent_orders = {}
        logger.debug("Initialized recent orders cache")
    
    # Clean old orders (older than 30 seconds)
    old_count = len(process_customer_order_tool._recent_orders)
    process_customer_order_tool._recent_orders = {
        k: v for k, v in process_customer_order_tool._recent_orders.items() 
        if current_time - v < 30
    }
    new_count = len(process_customer_order_tool._recent_orders)
    if old_count != new_count:
        logger.debug(f"Cleaned {old_count - new_count} old orders from cache")
    
    logger.debug(f"Recent orders in cache: {list(process_customer_order_tool._recent_orders.keys())}")
    
    if order_key in process_customer_order_tool._recent_orders:
        logger.warning(f"Duplicate order detected within 30 seconds - skipping: {order_key}")
        return json.dumps({
            "success": True, 
            "message": "Order already processed",
            "duplicate_prevention": True
        })
    
    # Record this order
    logger.info(f"Processing new order: {order_key}")
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
            "status": "Pending",  # Status starts as Pending for new orders
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
                    "product": product_details.get("product_name", product_name),  # Added for "Product" column
                    "item": product_details.get("product_name", product_name),  # Added for "Item" column
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
                print(f"[DEBUG] Looking for mappings for clean_header: '{clean_header}'")
                print(f"[DEBUG] Product details: {product_details}")
                print(f"[DEBUG] Available inventory mappings: {list(inventory_mappings.keys())}")
                for inv_key, inv_value in inventory_mappings.items():
                    print(f"[DEBUG] Checking {inv_key} -> {inv_value} (in '{clean_header}': {inv_key in clean_header})")
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
        
        # Create a beautiful order summary for the customer
        total_price = float(product_details.get("price", 0)) * quantity
        
        order_summary = f"""✅ Order Confirmed!

📋 Order Summary:
• Order ID: {customer_provided_data["order_id"]}
• Product: {product_details.get("product_name", product_name)}
• Quantity: {quantity}
• Price: PKR {product_details.get("price", "N/A")} each
• Total: PKR {total_price:,.0f}

👤 Customer Details:
• Name: {customer_name}
• Email: {customer_provided_data.get("customer_email", "Not provided")}
• Address: {customer_provided_data.get("address", "Not provided")}
• Payment: {customer_provided_data.get("payment_mode", "Not specified")}

📦 Status: Processing now!
Your order has been placed and inventory updated. Thank you for your purchase!"""

        return json.dumps({
            "success": True,
            "message": "Order processed successfully",
            "order_summary": order_summary,
            "order_details": {
                "order_id": customer_provided_data["order_id"],
                "customer_name": customer_name,
                "product_name": product_details.get("product_name", product_name),
                "quantity": quantity,
                "total_price": total_price,
                "previous_stock": available_quantity,
                "new_stock": new_quantity,
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

@mcp.tool()
def update_customer_order_tool(order_id: str, new_product_name: str = "", new_quantity: int = None, new_customer_name: str = "", new_customer_email: str = "", new_customer_address: str = "", new_payment_mode: str = "") -> str:
    """
    Update an existing customer order by ORDER ID with intelligent inventory synchronization.
    - Updates order details in orders sheet
    - Handles PRODUCT CHANGES: Restores old product stock + deducts new product stock
    - Handles QUANTITY CHANGES: Automatically adjusts inventory based on differences
    - Supports updating customer information (name, email, address, payment mode)
    - Intelligently maps new product details (price, category, etc.) when product changes
    """
    logger.info(f"Updating order: {order_id}")
    
    conn = load_connection()
    if not conn:
        return json.dumps({"success": False, "error": "no_connection_configured"})
    
    headers = get_http_headers()
    print(headers)

    inventory_config = conn.get("inventory")
    orders_config = conn.get("orders")
    refresh_token = conn.get("refresh_token")
    
    if not all([inventory_config, orders_config, refresh_token]):
        return json.dumps({"success": False, "error": "missing_configuration"})
    
    try:
        service = build_sheets_service_from_refresh(refresh_token)
        
        # Step 1: Get current orders data to find the order
        orders_data = get_sheet_data(
            service, 
            orders_config["workbook_id"], 
            orders_config["worksheet_name"],
            conn
        )
        
        # Step 2: Find the order to update
        order_found = False
        order_row_index = -1
        current_order_data = {}
        
        for idx, order in enumerate(orders_data["data"]):
            detected_cols = smart_column_detection(order, "all")
            if "id" in detected_cols and detected_cols["id"]["value"] == order_id:
                order_found = True
                order_row_index = idx + 2  # +2 because sheets are 1-indexed and we skip header
                current_order_data = detected_cols
                break
        
        if not order_found:
            return json.dumps({
                "success": False,
                "error": "order_not_found",
                "message": f"Order {order_id} not found"
            })
        
        # Step 3: Get current order details
        current_product_name = current_order_data.get("product_name", {}).get("value", "")
        current_quantity = int(current_order_data.get("quantity", {}).get("value", 0))
        
        print(f"[DEBUG] Found order {order_id}: {current_product_name} x{current_quantity}")
        
        # Step 4: Get inventory data for product lookups
        inventory_data = get_sheet_data(
            service, 
            inventory_config["workbook_id"], 
            inventory_config["worksheet_name"],
            conn
        )
        
        # Step 5: Handle PRODUCT CHANGE (most complex scenario)
        product_changed = new_product_name and new_product_name.lower() != current_product_name.lower()
        quantity_changed = new_quantity is not None and new_quantity != current_quantity
        final_quantity = new_quantity if new_quantity is not None else current_quantity
        
        new_product_details = {}
        
        if product_changed:
            print(f"[DEBUG] Product change detected: '{current_product_name}' -> '{new_product_name}'")
            
            # First: Restore original product inventory
            if current_product_name:
                for idx, item in enumerate(inventory_data["data"]):
                    detected_cols = smart_column_detection(item, "all")
                    if "product_name" in detected_cols:
                        if current_product_name.lower() in detected_cols["product_name"]["value"].lower():
                            # Safe integer conversion for original product inventory
                            original_quantity_value = detected_cols.get("quantity", {}).get("value", "0")
                            try:
                                current_stock = int(original_quantity_value)
                                has_original_numeric_inventory = True
                            except (ValueError, TypeError):
                                # Non-numeric inventory - skip restoration for service business
                                has_original_numeric_inventory = False
                                print(f"[DEBUG] Non-numeric original inventory: '{original_quantity_value}' - skipping restoration")
                            
                            if has_original_numeric_inventory:
                                restored_stock = current_stock + current_quantity
                                
                                # Update inventory for old product
                                product_row_index = idx + 2
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
                                        body={"values": [[str(restored_stock)]]}
                                    ).execute()
                                    print(f"[DEBUG] Restored old product inventory: {current_product_name} {current_stock} -> {restored_stock}")
                            else:
                                print(f"[DEBUG] Skipping original inventory restoration for service business: {current_product_name}")
                            break
            
            # Second: Find new product and get its details
            new_product_found = False
            for idx, item in enumerate(inventory_data["data"]):
                detected_cols = smart_column_detection(item, "all")
                if "product_name" in detected_cols:
                    if new_product_name.lower() in detected_cols["product_name"]["value"].lower():
                        new_product_found = True
                        new_product_details = {
                            "product_name": detected_cols["product_name"]["value"],
                            "price": detected_cols.get("price", {}).get("value", ""),
                            "category": detected_cols.get("category", {}).get("value", ""),
                            "size": detected_cols.get("size", {}).get("value", ""),
                            "color": detected_cols.get("color", {}).get("value", ""),
                            "weight": detected_cols.get("weight", {}).get("value", ""),  # Added weight
                            "description": detected_cols.get("description", {}).get("value", "")
                        }
                        
                        # Check availability for new product - handle non-numeric quantities (like "Daily")
                        quantity_value = detected_cols.get("quantity", {}).get("value", "0")
                        try:
                            available_stock = int(quantity_value)
                            has_numeric_inventory = True
                        except (ValueError, TypeError):
                            # Non-numeric inventory (like "Daily", "Available", "Limited") - skip inventory checks
                            available_stock = 999999  # Treat as unlimited for food/service businesses
                            has_numeric_inventory = False
                            print(f"[DEBUG] Non-numeric inventory detected: '{quantity_value}' - treating as service business")
                        
                        if has_numeric_inventory and available_stock < final_quantity:
                            return json.dumps({
                                "success": False,
                                "error": "insufficient_stock",
                                "message": f"New product '{new_product_name}' has only {available_stock} units available, but {final_quantity} requested."
                            })
                        
                        # Only update inventory for businesses with numeric stock tracking
                        if has_numeric_inventory:
                            # Deduct inventory for new product
                            new_stock = available_stock - final_quantity
                            product_row_index = idx + 2
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
                                    body={"values": [[str(new_stock)]]}
                                ).execute()
                                print(f"[DEBUG] Updated new product inventory: {new_product_name} {available_stock} -> {new_stock}")
                        else:
                            print(f"[DEBUG] Skipping inventory update for service business: {new_product_name}")
                        break
            
            if not new_product_found:
                return json.dumps({
                    "success": False,
                    "error": "new_product_not_found",
                    "message": f"New product '{new_product_name}' not found in inventory"
                })
        
        elif quantity_changed:
            # Step 6: Handle QUANTITY CHANGE ONLY (original logic)
            print(f"[DEBUG] Quantity change detected: {current_quantity} -> {new_quantity}")
            
            # Find current product in inventory
            for idx, item in enumerate(inventory_data["data"]):
                detected_cols = smart_column_detection(item, "all")
                if "product_name" in detected_cols:
                    if current_product_name.lower() in detected_cols["product_name"]["value"].lower():
                        # Safe integer conversion for quantity-only changes
                        quantity_value = detected_cols.get("quantity", {}).get("value", "0")
                        try:
                            current_stock = int(quantity_value)
                            has_numeric_stock = True
                        except (ValueError, TypeError):
                            # Non-numeric inventory - skip quantity changes for service business
                            has_numeric_stock = False
                            print(f"[DEBUG] Non-numeric inventory: '{quantity_value}' - skipping quantity adjustment for service business")
                        
                        if has_numeric_stock:
                            quantity_difference = new_quantity - current_quantity
                            new_stock = current_stock - quantity_difference
                            
                            print(f"[DEBUG] Inventory adjustment: {current_quantity} -> {new_quantity} (diff: {quantity_difference})")
                            print(f"[DEBUG] Stock adjustment: {current_stock} -> {new_stock}")
                            
                            # Check if we have enough stock for increase
                            if quantity_difference > 0 and current_stock < quantity_difference:
                                return json.dumps({
                                    "success": False,
                                    "error": "insufficient_stock",
                                    "message": f"Cannot increase quantity by {quantity_difference}. Only {current_stock} units available."
                                })
                            
                            # Update inventory
                            product_row_index = idx + 2
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
                                    body={"values": [[str(new_stock)]]}
                                ).execute()
                                print(f"[DEBUG] Inventory updated: {current_stock} -> {new_stock}")
                        else:
                            print(f"[DEBUG] Skipping quantity adjustment for service business")
                        break
                        break
        
        # Step 7: Update order details in orders sheet
        update_data = {}
        
        # Prepare update values based on what's provided
        if product_changed and new_product_details:
            # Calculate new total if product changed
            try:
                price_str = str(new_product_details.get("price", ""))
                price_numeric = ''.join(c for c in price_str if c.isdigit() or c == '.')
                if price_numeric:
                    unit_price = float(price_numeric)
                    new_total = str(unit_price * final_quantity)
                    print(f"[DEBUG] Calculated new total: {unit_price} × {final_quantity} = {new_total}")
                else:
                    new_total = ""
            except:
                new_total = ""
                
            update_data.update({
                "product": new_product_details["product_name"],
                "product_name": new_product_details["product_name"],
                "item": new_product_details["product_name"],
                "item_name": new_product_details["product_name"],
                "price": new_product_details["price"],
                "unit_price": new_product_details["price"], 
                "total": new_total,
                "subtotal": new_total,
                "category": new_product_details.get("category", ""),
                "size": new_product_details.get("size", ""),
                "color": new_product_details.get("color", ""),
                "weight": new_product_details.get("weight", ""),  # Added missing weight update
                "description": new_product_details.get("description", "")
            })
        
        if new_quantity is not None:
            update_data["quantity"] = str(new_quantity)
            update_data["qty"] = str(new_quantity)
        if new_customer_name:
            update_data["customer_name"] = new_customer_name
            update_data["customer"] = new_customer_name
        if new_customer_email:
            update_data["customer_email"] = new_customer_email  
            update_data["email"] = new_customer_email
        if new_customer_address:
            update_data["customer_address"] = new_customer_address
            update_data["address"] = new_customer_address
            update_data["delivery_address"] = new_customer_address
        if new_payment_mode:
            update_data["payment_mode"] = new_payment_mode
            update_data["payment_type"] = new_payment_mode
            update_data["payment"] = new_payment_mode
        
        # Update each column that has new data
        orders_headers = orders_data["headers"]
        updates_applied = []
        
        for col_idx, header in enumerate(orders_headers):
            clean_header = header.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
            
            # Find matching update data
            for update_key, update_value in update_data.items():
                if update_value and (update_key in clean_header or clean_header in update_key):
                    col_letter = chr(65 + col_idx)  # A=0, B=1, etc.
                    range_name = f"{orders_config['worksheet_name']}!{col_letter}{order_row_index}"
                    
                    service.spreadsheets().values().update(
                        spreadsheetId=orders_config["workbook_id"],
                        range=range_name,
                        valueInputOption="RAW",
                        body={"values": [[update_value]]}
                    ).execute()
                    print(f"[DEBUG] Updated {header}: {update_value}")
                    updates_applied.append(f"{header}: {update_value}")
                    break
        
        # Step 8: Return success response
        final_product_name = new_product_details.get("product_name", current_product_name) if product_changed else current_product_name
        
        return json.dumps({
            "success": True,
            "message": f"Order {order_id} updated successfully",
            "order_id": order_id,
            "updates_applied": updates_applied,
            "product_changed": product_changed,
            "inventory_adjusted": product_changed or quantity_changed,
            "order_summary": f"""
📋 ORDER UPDATED SUCCESSFULLY!

🆔 Order ID: {order_id}
📦 Product: {f'{current_product_name} → {final_product_name}' if product_changed else final_product_name}
🔢 Quantity: {f'{current_quantity} → {final_quantity}' if quantity_changed else final_quantity}
👤 Customer: {new_customer_name if new_customer_name else 'unchanged'}
📧 Email: {new_customer_email if new_customer_email else 'unchanged'}
💳 Payment: {new_payment_mode if new_payment_mode else 'unchanged'}
📍 Address: {new_customer_address if new_customer_address else 'unchanged'}

✅ Your order has been updated and inventory synchronized!
{f'💰 New Price: {new_product_details.get("price", "")} PKR' if product_changed else ''}"""
        })
        
    except Exception as e:
        logger.error(f"Order update failed: {e}")
        return json.dumps({
            "success": False,
            "error": "update_failed",
            "details": str(e)
        })

@mcp.tool()
def cancel_customer_order_tool(order_id: str) -> str:
    """
    Cancel an existing customer order by ORDER ID and restore inventory.
    - Marks order status as 'Cancelled' instead of deleting the row
    - Restores full quantity back to inventory
    - Preserves order history for business records and analytics
    """
    logger.info(f"Cancelling order: {order_id}")
    
    conn = load_connection()
    if not conn:
        return json.dumps({"success": False, "error": "no_connection_configured"})
    
    inventory_config = conn.get("inventory")
    orders_config = conn.get("orders")
    refresh_token = conn.get("refresh_token")
    
    if not all([inventory_config, orders_config, refresh_token]):
        return json.dumps({"success": False, "error": "missing_configuration"})
    
    try:
        service = build_sheets_service_from_refresh(refresh_token)
        
        # Step 1: Get current orders data to find the order
        orders_data = get_sheet_data(
            service, 
            orders_config["workbook_id"], 
            orders_config["worksheet_name"],
            conn
        )
        
        # Step 2: Find the order to cancel
        order_found = False
        order_row_index = -1
        order_details = {}
        
        for idx, order in enumerate(orders_data["data"]):
            detected_cols = smart_column_detection(order, "all")
            if "id" in detected_cols and detected_cols["id"]["value"] == order_id:
                order_found = True
                order_row_index = idx + 2  # +2 because sheets are 1-indexed and we skip header
                order_details = {
                    "product_name": detected_cols.get("product_name", {}).get("value", ""),
                    "quantity": int(detected_cols.get("quantity", {}).get("value", 0)),
                    "customer_name": detected_cols.get("customer_name", {}).get("value", ""),
                    "total": detected_cols.get("price", {}).get("value", "")
                }
                break
        
        if not order_found:
            return json.dumps({
                "success": False, 
                "error": "order_not_found",
                "message": f"Order {order_id} not found"
            })
        
        print(f"[DEBUG] Found order to cancel: {order_details}")
        
        # Step 3: Check current order status before cancelling
        current_status = ""
        for idx, order in enumerate(orders_data["data"]):
            if idx + 2 == order_row_index:
                detected_cols = smart_column_detection(order, "all")
                current_status = detected_cols.get("status", {}).get("value", "").strip()
                print(f"[DEBUG] Current order status: '{current_status}'")
                break
        
        # Only allow cancelling Pending orders
        if current_status.lower() == "cancelled":
            return json.dumps({
                "success": False,
                "error": "already_cancelled", 
                "message": f"Order {order_id} is already cancelled"
            })
        elif current_status.lower() == "delivered":
            return json.dumps({
                "success": False,
                "error": "cannot_cancel_delivered", 
                "message": f"Order {order_id} has already been delivered and cannot be cancelled"
            })
        elif current_status and current_status.lower() not in ["pending", ""]:
            return json.dumps({
                "success": False,
                "error": "invalid_status_for_cancellation", 
                "message": f"Order {order_id} has status '{current_status}' and cannot be cancelled"
            })
        
        # Step 4: Restore inventory - add back the quantity that was deducted
        product_name = order_details["product_name"]
        quantity_to_restore = order_details["quantity"]
        
        if product_name and quantity_to_restore > 0:
            # Get inventory data
            inventory_data = get_sheet_data(
                service, 
                inventory_config["workbook_id"], 
                inventory_config["worksheet_name"],
                conn
            )
            
            # Find the product in inventory
            product_found = False
            product_row_index = -1
            current_stock = 0
            
            for idx, item in enumerate(inventory_data["data"]):
                detected_cols = smart_column_detection(item, "all")
                if "product_name" in detected_cols:
                    if product_name.lower() in detected_cols["product_name"]["value"].lower():
                        product_found = True
                        product_row_index = idx + 2
                        if "quantity" in detected_cols:
                            # Safe integer conversion for cancellation restoration
                            cancel_quantity_value = detected_cols["quantity"]["value"] or "0"
                            try:
                                current_stock = int(cancel_quantity_value)
                                has_cancel_numeric_inventory = True
                            except (ValueError, TypeError):
                                # Non-numeric inventory - skip restoration for service business
                                has_cancel_numeric_inventory = False
                                print(f"[DEBUG] Non-numeric cancel inventory: '{cancel_quantity_value}' - skipping restoration for service business")
                        break
            
            if product_found and has_cancel_numeric_inventory:
                # Restore inventory by adding back the cancelled quantity
                new_stock = current_stock + quantity_to_restore
                
                print(f"[DEBUG] Restoring inventory: {current_stock} + {quantity_to_restore} = {new_stock}")
                
                # Update inventory
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
                        body={"values": [[str(new_stock)]]}
                    ).execute()
                    print(f"[DEBUG] Inventory restored: {current_stock} -> {new_stock}")
        
        # Step 5: Update order status from 'Pending' to 'Cancelled'
        orders_headers = orders_data["headers"]
        status_col = None
        
        # Find the existing status column
        for col_idx, header in enumerate(orders_headers):
            if "status" in header.lower():
                status_col = chr(65 + col_idx)  # A=0, B=1, etc.
                break
        
        if status_col:
            # Update the existing status column to 'Cancelled'
            range_name = f"{orders_config['worksheet_name']}!{status_col}{order_row_index}"
            service.spreadsheets().values().update(
                spreadsheetId=orders_config["workbook_id"],
                range=range_name,
                valueInputOption="RAW",
                body={"values": [["Cancelled"]]}
            ).execute()
            print(f"[DEBUG] Order status updated from 'Pending' to 'Cancelled' in column {status_col}")
        else:
            print(f"[DEBUG] Warning: No Status column found in orders sheet")
            # Still proceed with cancellation even if status column not found
        # Step 6: Return success response  
        return json.dumps({
            "success": True,
            "message": f"Order {order_id} cancelled successfully",
            "order_id": order_id,
            "cancelled_details": order_details,
            "inventory_restored": quantity_to_restore > 0,
            "order_summary": f"""
❌ ORDER CANCELLED SUCCESSFULLY!

🆔 Cancelled Order: {order_id}
📦 Product: {product_name}
🔢 Quantity: {quantity_to_restore}
👤 Customer: {order_details['customer_name']}

✅ Order marked as 'Cancelled' and {quantity_to_restore} units restored to inventory!
📋 Order preserved for business records."""
        })
        
    except Exception as e:
        logger.error(f"Order cancellation failed: {e}")
        return json.dumps({
            "success": False,
            "error": "cancellation_failed",
            "details": str(e)
        })


@mcp.tool()
def say_hello(name: str) -> str:

    headers = get_http_headers()
    print(headers)
    return f"Hello, {name}!, \nHeaders, {headers}"

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