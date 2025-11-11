import os, json, time
import logging
import requests
import base64
import uuid
from io import BytesIO
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import gspread
import psycopg2
from imagekitio import ImageKit
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from cryptography.fernet import Fernet

from fastmcp import FastMCP

# Load environment variables
load_dotenv()

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

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")

mcp = FastMCP(
    name="Google Sheets MCP",
    stateless_http=True,
)

FERNET_KEY = os.getenv("FERNET_KEY")

def decrypt_if_needed(token_enc: str) -> str:
    logger.debug(f"Decrypting token... FERNET_KEY exists: {bool(FERNET_KEY)}")
    if not token_enc:
        logger.error("No token provided for decryption")
        return None
    # Encryption disabled for development
    logger.debug("Encryption disabled, returning token as-is")
    return token_enc

def load_env_connection():
    """Load connection data from environment variables"""
    return {
        "inventory": {
            "workbook_id": os.getenv("INVENTORY_SHEET_ID"),
            "worksheet_name": os.getenv("INVENTORY_WORKSHEET_NAME")
        },
        "orders": {
            "workbook_id": os.getenv("ORDERS_SHEET_ID"),
            "worksheet_name": os.getenv("ORDERS_WORKSHEET_NAME")
        },
        "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN")
    }

def ensure_poster_table_exists():
    """
    Ensure the poster_generations table exists in Neon Postgres database.
    Creates the table if it doesn't exist.
    Returns a database connection object.
    """
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise Exception("DATABASE_URL not found in environment variables")
        
        # Connect to Neon Postgres
        conn = psycopg2.connect(database_url, sslmode='require')
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS poster_generations (
                id SERIAL PRIMARY KEY,
                created_date TIMESTAMP DEFAULT NOW(),
                tenant_id VARCHAR(255) NOT NULL,
                image_url TEXT NOT NULL,
                image_caption TEXT
            );
        """)
        
        # Create index for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tenant_date 
            ON poster_generations(tenant_id, created_date DESC);
        """)
        
        conn.commit()
        logger.info("Poster generations table ensured to exist")
        
        return conn
        
    except Exception as e:
        logger.error(f"Database table creation failed: {e}")
        raise

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

def build_google_credentials_from_refresh(refresh_token):
    """Build Google credentials object that can be used for any Google service (Sheets, Gmail, etc.)"""
    logger.debug("Building Google credentials from refresh token...")
    
    # Decrypt the refresh token if needed
    decrypted_token = decrypt_if_needed(refresh_token)
    
    creds = Credentials(
        token=None,
        refresh_token=decrypted_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/gmail.send"
        ]
    )
    
    try:
        # Refresh to get an access token
        creds.refresh(Request())
        logger.debug("Google credentials refresh successful")
        return creds
    except Exception as refresh_error:
        logger.error(f"Google credentials refresh failed: {refresh_error}")
        raise

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
def process_customer_order_tool(customer_name: str, product_name: str, quantity: int, customer_email: str = "", customer_address: str = "", payment_mode: str = "") -> str:
    """
    Complete end-to-end order processing with dynamic schema analysis.
    Automatically detects orders sheet columns and fills them with inventory data or provided customer data.
    Returns detailed info about what customer information is still needed.
    Processes single product/item orders
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
    
    conn = load_env_connection()
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
    
    conn = load_env_connection()
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
    Update an existing customer order by ORDER ID with intelligent inventory synchronization. (For single product/item orders)
    - Updates order details in orders sheet
    - Handles PRODUCT CHANGES: Restores old product stock + deducts new product stock
    - Handles QUANTITY CHANGES: Automatically adjusts inventory based on differences
    - Supports updating customer information (name, email, address, payment mode)
    - Intelligently maps new product details (price, category, etc.) when product changes
    """
    logger.info(f"Updating order: {order_id}")
    
    conn = load_env_connection()
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
        quantity_value = current_order_data.get("quantity", {}).get("value", "0")
        
        # Check if this is a multiple products order (contains commas)
        if "," in str(quantity_value) or "," in current_product_name:
            return json.dumps({
                "success": False,
                "error": "multiple_products_order_detected",
                "message": f"Order {order_id} contains multiple products. Please use update_multiple_products_order_tool() instead of update_customer_order_tool().",
                "suggested_tool": "update_multiple_products_order_tool",
                "order_details": {
                    "order_id": order_id,
                    "products": current_product_name,
                    "quantities": quantity_value
                }
            })
        
        current_quantity = int(quantity_value)
        
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
    Cancel an existing customer order by ORDER ID and restore inventory. For single item/product orders.
    - Marks order status as 'Cancelled' instead of deleting the row
    - Restores full quantity back to inventory
    - Preserves order history for business records and analytics
    """
    logger.info(f"Cancelling order: {order_id}")
    
    conn = load_env_connection()
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
def process_multiple_products_order_tool(customer_name: str, products_list: str, customer_email: str = "", customer_address: str = "", payment_mode: str = "") -> str:
    """
    Process customer orders with MULTIPLE products/items at once in a single order.
    Perfect for real-world scenarios: food orders (pizza+fries+coke), skincare bundles, wardrobe combinations, etc.
    
    Products format: "Product1:Quantity1,Product2:Quantity2,Product3:Quantity3"
    Example: "Pizza:2,Fries:1,Coke:3" or "Face Wash:1,Moisturizer:2,Sunscreen:1"
    
    Features:
    - Single order ID for all products
    - Consolidated inventory management 
    - Dynamic business type support (inventory vs service businesses)
    - Intelligent error handling per product
    - Beautiful order summary with total calculation
    """
    logger.info(f"Multiple products order: {customer_name} wants {products_list}")
    
    # Order deduplication for multiple products
    current_time = time.time()
    order_key = f"{customer_name}_{products_list}_{customer_email}_{customer_address}"
    
    # Check for recent duplicate orders
    if not hasattr(process_multiple_products_order_tool, '_recent_orders'):
        process_multiple_products_order_tool._recent_orders = {}
    
    # Clean old orders (older than 30 seconds)
    process_multiple_products_order_tool._recent_orders = {
        k: v for k, v in process_multiple_products_order_tool._recent_orders.items() 
        if current_time - v < 30
    }
    
    if order_key in process_multiple_products_order_tool._recent_orders:
        logger.warning(f"Duplicate multiple products order detected - skipping: {order_key}")
        return json.dumps({
            "success": True, 
            "message": "Order already processed",
            "duplicate_prevention": True
        })
    
    # Record this order
    process_multiple_products_order_tool._recent_orders[order_key] = current_time
    
    conn = load_env_connection()
    if not conn:
        return json.dumps({"success": False, "error": "no_connection_configured"})
    
    inventory_config = conn.get("inventory")
    orders_config = conn.get("orders")
    refresh_token = conn.get("refresh_token")
    
    if not all([inventory_config, orders_config, refresh_token]):
        return json.dumps({"success": False, "error": "missing_configuration"})
    
    try:
        # Parse products list: "Pizza:2,Fries:1,Coke:3"
        products_data = []
        try:
            for item in products_list.split(','):
                if ':' in item:
                    product, qty = item.strip().split(':', 1)
                    products_data.append({
                        "name": product.strip(),
                        "quantity": int(qty.strip())
                    })
                else:
                    return json.dumps({
                        "success": False,
                        "error": "invalid_format",
                        "message": "Products format should be 'Product1:Quantity1,Product2:Quantity2'. Example: 'Pizza:2,Fries:1'"
                    })
        except ValueError as e:
            return json.dumps({
                "success": False,
                "error": "parsing_error", 
                "message": f"Error parsing products list: {str(e)}. Use format 'Product1:Quantity1,Product2:Quantity2'"
            })
        
        if not products_data:
            return json.dumps({
                "success": False,
                "error": "empty_products",
                "message": "No products specified"
            })
        
        print(f"[DEBUG] Parsed products: {products_data}")
        
        # Single Google Sheets service connection
        service = build_sheets_service_from_refresh(refresh_token)
        
        # Get inventory data once
        inventory_data = get_sheet_data(
            service, 
            inventory_config["workbook_id"], 
            inventory_config["worksheet_name"],
            conn
        )
        
        # Get orders sheet schema
        orders_data = get_sheet_data(
            service,
            orders_config["workbook_id"],
            orders_config["worksheet_name"],
            conn
        )
        orders_headers = orders_data["headers"]
        
        # Check if inventory has quantity tracking
        inventory_headers = inventory_data["headers"]
        has_quantity_column = any("quantity" in header.lower() or "stock" in header.lower() or "available" in header.lower() for header in inventory_headers)
        print(f"[DEBUG] Inventory has quantity tracking: {has_quantity_column}")
        
        # Step 1: Validate ALL products first (fail fast if any product unavailable)
        validated_products = []
        total_order_amount = 0
        products_summary = []
        
        for product_item in products_data:
            product_name = product_item["name"]
            quantity = product_item["quantity"]
            
            # Find product in inventory
            product_found = False
            product_details = {}
            
            for idx, item in enumerate(inventory_data["data"]):
                detected_cols = smart_column_detection(item, "all")
                
                if "product_name" in detected_cols:
                    inventory_product_name = detected_cols["product_name"]["value"]
                    if product_name.lower() in inventory_product_name.lower():
                        product_found = True
                        
                        # Extract all product details
                        product_details = {
                            "inventory_name": inventory_product_name,
                            "price": detected_cols.get("price", {}).get("value", ""),
                            "category": detected_cols.get("category", {}).get("value", ""),
                            "size": detected_cols.get("size", {}).get("value", ""),
                            "color": detected_cols.get("color", {}).get("value", ""),
                            "weight": detected_cols.get("weight", {}).get("value", ""),
                            "description": detected_cols.get("description", {}).get("value", ""),
                            "row_index": idx + 2  # For later inventory update
                        }
                        
                        # Check availability (with safe integer conversion)
                        if has_quantity_column and "quantity" in detected_cols:
                            quantity_value = detected_cols["quantity"]["value"] or "0"
                            try:
                                available_stock = int(quantity_value)
                                has_numeric_inventory = True
                            except (ValueError, TypeError):
                                # Non-numeric inventory - treat as unlimited (service business)
                                available_stock = 999999
                                has_numeric_inventory = False
                                print(f"[DEBUG] Non-numeric inventory '{quantity_value}' for {product_name} - treating as service business")
                            
                            if has_numeric_inventory and available_stock < quantity:
                                return json.dumps({
                                    "success": False,
                                    "error": "insufficient_stock",
                                    "message": f"Product '{product_name}' has only {available_stock} units available, but {quantity} requested.",
                                    "product": product_name,
                                    "available": available_stock,
                                    "requested": quantity
                                })
                            
                            product_details["available_stock"] = available_stock
                            product_details["has_numeric_inventory"] = has_numeric_inventory
                        else:
                            # No quantity tracking - service business
                            product_details["available_stock"] = 999999
                            product_details["has_numeric_inventory"] = False
                        
                        # Calculate price
                        try:
                            price_str = str(product_details.get("price", ""))
                            price_numeric = ''.join(c for c in price_str if c.isdigit() or c == '.')
                            if price_numeric:
                                unit_price = float(price_numeric)
                                item_total = unit_price * quantity
                                total_order_amount += item_total
                                product_details["unit_price"] = unit_price
                                product_details["item_total"] = item_total
                        except:
                            product_details["unit_price"] = 0
                            product_details["item_total"] = 0
                        
                        break
            
            if not product_found:
                return json.dumps({
                    "success": False,
                    "error": "product_not_found",
                    "message": f"Product '{product_name}' not found in inventory",
                    "product": product_name
                })
            
            # Add to validated products
            validated_products.append({
                "name": product_name,
                "quantity": quantity,
                "details": product_details
            })
            
            # Add to summary
            products_summary.append(f"• {product_details['inventory_name']}: {quantity} × PKR {product_details.get('unit_price', 0)} = PKR {product_details.get('item_total', 0)}")
        
        print(f"[DEBUG] All {len(validated_products)} products validated successfully")
        print(f"[DEBUG] Total order amount: PKR {total_order_amount}")
        
        # Step 2: Generate order ID and prepare customer data
        order_id = f"ORD-{int(time.time())}"
        
        # Create consolidated products strings for storage
        products_names_list = [p["details"]["inventory_name"] for p in validated_products]
        quantities_list = [str(p["quantity"]) for p in validated_products]
        
        products_names_str = ",".join(products_names_list)
        quantities_str = ",".join(quantities_list)
        
        print(f"[DEBUG] Consolidated data:")
        print(f"[DEBUG]   Products: {products_names_str}")
        print(f"[DEBUG]   Quantities: {quantities_str}")
        
        # Step 3: Update inventory for all products
        inventory_updates = []
        for product in validated_products:
            product_details = product["details"]
            
            if product_details.get("has_numeric_inventory", False):
                old_stock = product_details["available_stock"]
                new_stock = old_stock - product["quantity"]
                row_index = product_details["row_index"]
                
                # Find quantity column
                quantity_col = None
                for col_letter, header in enumerate(inventory_data["headers"], start=1):
                    if any(word in header.lower() for word in ["quantity", "qty", "stock"]):
                        quantity_col = chr(64 + col_letter)
                        break
                
                if quantity_col and row_index > 0:
                    range_name = f"{inventory_config['worksheet_name']}!{quantity_col}{row_index}"
                    service.spreadsheets().values().update(
                        spreadsheetId=inventory_config["workbook_id"],
                        range=range_name,
                        valueInputOption="RAW",
                        body={"values": [[str(new_stock)]]}
                    ).execute()
                    
                    inventory_updates.append(f"{product['name']}: {old_stock} → {new_stock}")
                    print(f"[DEBUG] Updated inventory: {product['name']} {old_stock} → {new_stock}")
            else:
                print(f"[DEBUG] Skipping inventory update for service business: {product['name']}")
        
        # Step 4: Dynamic order row creation with consolidated data
        customer_provided_data = {
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_address": customer_address,
            "payment_mode": payment_mode,
            "status": "Pending",
            "order_id": order_id,
            "products": products_names_str,  # Consolidated products
            "quantities": quantities_str,    # Consolidated quantities  
            "total_amount": str(total_order_amount)
        }
        
        # Build order row using smart column detection
        order_row_data = []
        for header in orders_headers:
            clean_header = header.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
            value = ""
            
            # Map consolidated multiple products data
            if any(term in clean_header for term in ["product", "item", "name"]) and "customer" not in clean_header:
                value = products_names_str
            elif any(term in clean_header for term in ["weight"]):
                # Combine weights from all products
                weights_list = []
                for product in validated_products:
                    product_weight = product["details"].get("weight", "")
                    weights_list.append(product_weight if product_weight else "")
                value = ",".join(weights_list)
            elif any(term in clean_header for term in ["quantity", "qty"]):
                value = quantities_str
            elif any(term in clean_header for term in ["total", "amount", "price"]) and not any(term in clean_header for term in ["unit", "each"]):
                value = str(total_order_amount)
            elif any(term in clean_header for term in ["customer_name", "customer"]) and "email" not in clean_header:
                value = customer_name
            elif any(term in clean_header for term in ["email"]) and "customer" not in clean_header:
                value = customer_email
            elif any(term in clean_header for term in ["customer_email", "customer_email"]):
                value = customer_email
            elif any(term in clean_header for term in ["address", "delivery"]):
                value = customer_address
            elif any(term in clean_header for term in ["payment", "mode"]):
                value = payment_mode
            elif any(term in clean_header for term in ["status"]):
                value = "Pending"
            elif any(term in clean_header for term in ["order_id", "order_no", "order"]):
                value = order_id
            
            order_row_data.append(value)
            print(f"[DEBUG] Column '{header}': '{value}'")
        
        # Step 5: Add order to orders sheet
        orders_table_structure = orders_config.get("table_structure", {})
        start_col = orders_table_structure.get("start_col", 0)
        headers = orders_table_structure.get("headers", [])
        
        if len(headers) == 0:
            append_range = f"{orders_config['worksheet_name']}!A:Z"
        else:
            start_col_letter = chr(65 + start_col)
            end_col_letter = chr(65 + start_col + len(headers) - 1)
            append_range = f"{orders_config['worksheet_name']}!{start_col_letter}:{end_col_letter}"
        
        append_result = service.spreadsheets().values().append(
            spreadsheetId=orders_config["workbook_id"],
            range=append_range,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [order_row_data]}
        ).execute()
        
        print(f"[DEBUG] Multiple products order added successfully")
        
        # Step 6: Create beautiful order summary
        products_summary_str = "\n".join(products_summary)
        
        order_summary = f"""✅ MULTIPLE PRODUCTS ORDER CONFIRMED!

📋 Order Summary:
• Order ID: {order_id}
• Customer: {customer_name}
• Products Ordered:
{products_summary_str}

💰 Total Amount: PKR {total_order_amount:,.0f}

👤 Customer Details:
• Email: {customer_email or "Not provided"}
• Address: {customer_address or "Not provided"}  
• Payment: {payment_mode or "Not specified"}

📦 Status: Processing now!
Your multiple products order has been placed and inventory updated. Thank you for your purchase!"""

        return json.dumps({
            "success": True,
            "message": f"Multiple products order processed successfully - {len(validated_products)} items",
            "order_summary": order_summary,
            "order_details": {
                "order_id": order_id,
                "customer_name": customer_name,
                "products_count": len(validated_products),
                "products": products_names_str,
                "quantities": quantities_str,
                "total_amount": total_order_amount,
                "inventory_updates": inventory_updates,
                "complete_order_data": dict(zip(orders_headers, order_row_data))
            },
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"Multiple products order processing failed: {e}")
        return json.dumps({
            "success": False,
            "error": "processing_failed",
            "details": str(e)
        })

@mcp.tool()
def update_multiple_products_order_tool(order_id: str, new_products_list: str = "", new_customer_name: str = "", new_customer_email: str = "", new_customer_address: str = "", new_payment_mode: str = "") -> str:
    """
    Update an existing multiple products order by ORDER ID with intelligent inventory synchronization.
    - Handles complete product list changes: restores old products + deducts new products
    - Supports updating customer information (name, email, address, payment mode)
    - Dynamically works with any business type (inventory vs service businesses)
    
    Products format for changes: "Product1:Quantity1,Product2:Quantity2,Product3:Quantity3"
    Example: "Pizza:3,Burger:1,Coke:2" (replaces entire order with new products)
    """
    logger.info(f"Updating multiple products order: {order_id}")
    
    conn = load_env_connection()
    if not conn:
        return json.dumps({"success": False, "error": "no_connection_configured"})
    
    inventory_config = conn.get("inventory")
    orders_config = conn.get("orders")
    refresh_token = conn.get("refresh_token")
    
    if not all([inventory_config, orders_config, refresh_token]):
        return json.dumps({"success": False, "error": "missing_configuration"})
    
    try:
        service = build_sheets_service_from_refresh(refresh_token)
        
        # Step 1: Find the order
        orders_data = get_sheet_data(
            service, 
            orders_config["workbook_id"], 
            orders_config["worksheet_name"],
            conn
        )
        
        order_found = False
        order_row_index = -1
        current_order_data = {}
        
        for idx, order in enumerate(orders_data["data"]):
            detected_cols = smart_column_detection(order, "all")
            if "id" in detected_cols and detected_cols["id"]["value"] == order_id:
                order_found = True
                order_row_index = idx + 2
                current_order_data = detected_cols
                break
        
        if not order_found:
            return json.dumps({
                "success": False,
                "error": "order_not_found",
                "message": f"Order {order_id} not found"
            })
        
        # Step 2: Parse current order products
        current_products_str = current_order_data.get("product_name", {}).get("value", "")
        current_quantities_str = current_order_data.get("quantity", {}).get("value", "")
        
        print(f"[DEBUG] Current order products: {current_products_str}")
        print(f"[DEBUG] Current order quantities: {current_quantities_str}")
        
        # Parse current products for inventory restoration
        current_products = []
        if current_products_str and current_quantities_str:
            product_names = current_products_str.split(',')
            quantities = current_quantities_str.split(',')
            
            for i, product_name in enumerate(product_names):
                if i < len(quantities):
                    try:
                        qty = int(quantities[i].strip())
                        current_products.append({
                            "name": product_name.strip(),
                            "quantity": qty
                        })
                    except ValueError:
                        continue
        
        # Step 3: If new products list provided, handle product changes
        if new_products_list:
            # Parse new products
            try:
                new_products = []
                for item in new_products_list.split(','):
                    if ':' in item:
                        product, qty = item.strip().split(':', 1)
                        new_products.append({
                            "name": product.strip(),
                            "quantity": int(qty.strip())
                        })
            except ValueError as e:
                return json.dumps({
                    "success": False,
                    "error": "parsing_error",
                    "message": f"Error parsing new products list: {str(e)}"
                })
            
            # Get inventory data
            inventory_data = get_sheet_data(
                service, 
                inventory_config["workbook_id"], 
                inventory_config["worksheet_name"],
                conn
            )
            
            # Step 4: Smart inventory management - only process differences
            # Compare old vs new products to identify what actually changed
            old_product_dict = {p["name"].lower(): p["quantity"] for p in current_products}
            new_product_dict = {p["name"].lower(): p["quantity"] for p in new_products}
            
            print(f"[DEBUG] Old products: {old_product_dict}")
            print(f"[DEBUG] New products: {new_product_dict}")
            
            # Products to restore (only those removed or with reduced quantities)
            products_to_restore = []
            for old_name, old_qty in old_product_dict.items():
                if old_name not in new_product_dict:
                    # Product completely removed - restore full quantity
                    products_to_restore.append({"name": old_name, "quantity": old_qty, "reason": "removed"})
                elif new_product_dict[old_name] < old_qty:
                    # Product quantity reduced - restore the difference
                    qty_difference = old_qty - new_product_dict[old_name]
                    products_to_restore.append({"name": old_name, "quantity": qty_difference, "reason": "reduced"})
            
            # Products to deduct (only those added or with increased quantities)
            products_to_deduct = []
            for new_name, new_qty in new_product_dict.items():
                if new_name not in old_product_dict:
                    # Product completely new - deduct full quantity
                    products_to_deduct.append({"name": new_name, "quantity": new_qty, "reason": "added"})
                elif new_qty > old_product_dict[new_name]:
                    # Product quantity increased - deduct the difference
                    qty_difference = new_qty - old_product_dict[new_name]
                    products_to_deduct.append({"name": new_name, "quantity": qty_difference, "reason": "increased"})
            
            print(f"[DEBUG] Products to restore: {products_to_restore}")
            print(f"[DEBUG] Products to deduct: {products_to_deduct}")
            
            # Step 5: Restore inventory for products that need restoration
            for restore_item in products_to_restore:
                product_name = restore_item["name"]
                quantity_to_restore = restore_item["quantity"]
                
                for idx, item in enumerate(inventory_data["data"]):
                    detected_cols = smart_column_detection(item, "all")
                    if "product_name" in detected_cols:
                        if product_name.lower() in detected_cols["product_name"]["value"].lower():
                            # Safe integer conversion for restoration
                            quantity_value = detected_cols.get("quantity", {}).get("value", "0")
                            try:
                                current_stock = int(quantity_value)
                                has_numeric_inventory = True
                            except (ValueError, TypeError):
                                has_numeric_inventory = False
                                print(f"[DEBUG] Non-numeric inventory for restoration: {product_name}")
                            
                            if has_numeric_inventory:
                                restored_stock = current_stock + quantity_to_restore
                                
                                # Update inventory
                                product_row_index = idx + 2
                                quantity_col = None
                                for col_letter, header in enumerate(inventory_data["headers"], start=1):
                                    if any(word in header.lower() for word in ["quantity", "qty", "stock"]):
                                        quantity_col = chr(64 + col_letter)
                                        break
                                
                                if quantity_col:
                                    range_name = f"{inventory_config['worksheet_name']}!{quantity_col}{product_row_index}"
                                    service.spreadsheets().values().update(
                                        spreadsheetId=inventory_config["workbook_id"],
                                        range=range_name,
                                        valueInputOption="RAW",
                                        body={"values": [[str(restored_stock)]]}
                                    ).execute()
                                    print(f"[DEBUG] Restored {restore_item['reason']} product: {product_name} +{quantity_to_restore} ({current_stock} → {restored_stock})")
                            break
            
            # Step 6: Validate and deduct inventory for products that need deduction
            validated_new_products = []
            total_new_amount = 0
            
            for deduct_item in products_to_deduct:
                product_name = deduct_item["name"]
                quantity_to_deduct = deduct_item["quantity"]
                
                # Find product in inventory
                product_found = False
                for idx, item in enumerate(inventory_data["data"]):
                    detected_cols = smart_column_detection(item, "all")
                    if "product_name" in detected_cols:
                        if product_name.lower() in detected_cols["product_name"]["value"].lower():
                            product_found = True
                            
                            # Check availability
                            quantity_value = detected_cols.get("quantity", {}).get("value", "0")
                            try:
                                available_stock = int(quantity_value)
                                has_numeric_inventory = True
                            except (ValueError, TypeError):
                                available_stock = 999999
                                has_numeric_inventory = False
                            
                            if has_numeric_inventory and available_stock < quantity_to_deduct:
                                return json.dumps({
                                    "success": False,
                                    "error": "insufficient_stock",
                                    "message": f"Product '{product_name}' has only {available_stock} units available, need {quantity_to_deduct} more"
                                })
                            
                            # Deduct inventory
                            if has_numeric_inventory:
                                new_stock = available_stock - quantity_to_deduct
                                product_row_index = idx + 2
                                quantity_col = None
                                for col_letter, header in enumerate(inventory_data["headers"], start=1):
                                    if any(word in header.lower() for word in ["quantity", "qty", "stock"]):
                                        quantity_col = chr(64 + col_letter)
                                        break
                                
                                if quantity_col:
                                    range_name = f"{inventory_config['worksheet_name']}!{quantity_col}{product_row_index}"
                                    service.spreadsheets().values().update(
                                        spreadsheetId=inventory_config["workbook_id"],
                                        range=range_name,
                                        valueInputOption="RAW",
                                        body={"values": [[str(new_stock)]]}
                                    ).execute()
                                    print(f"[DEBUG] Deducted {deduct_item['reason']} product: {product_name} -{quantity_to_deduct} ({available_stock} → {new_stock})")
                            break
                
                if not product_found:
                    return json.dumps({
                        "success": False,
                        "error": "new_product_not_found",
                        "message": f"Product '{product_name}' not found in inventory"
                    })
            
            # Step 7: Calculate total for all new products and collect product details
            for new_product in new_products:
                product_name = new_product["name"]
                quantity = new_product["quantity"]
                
                # Find product details for price calculation
                for idx, item in enumerate(inventory_data["data"]):
                    detected_cols = smart_column_detection(item, "all")
                    if "product_name" in detected_cols:
                        if product_name.lower() in detected_cols["product_name"]["value"].lower():
                            # Calculate new total
                            price_str = str(detected_cols.get("price", {}).get("value", ""))
                            price_numeric = ''.join(c for c in price_str if c.isdigit() or c == '.')
                            if price_numeric:
                                unit_price = float(price_numeric)
                                total_new_amount += unit_price * quantity
                            
                            validated_new_products.append({
                                "name": detected_cols["product_name"]["value"],
                                "quantity": quantity,
                                "weight": detected_cols.get("weight", {}).get("value", "")
                            })
                            break
            
            # Step 8: Update order with new products
            new_products_str = ",".join([p["name"] for p in validated_new_products])
            new_quantities_str = ",".join([str(p["quantity"]) for p in validated_new_products])
            new_weights_str = ",".join([p.get("weight", "") for p in validated_new_products])
            
            # Update order sheet
            orders_headers = orders_data["headers"]
            updates_applied = []
            
            update_data = {
                "product": new_products_str,
                "product_name": new_products_str,
                "item": new_products_str,
                "weight": new_weights_str,
                "quantity": new_quantities_str,
                "qty": new_quantities_str,
                "total": str(total_new_amount),
                "amount": str(total_new_amount)
            }
            
            # Add customer updates if provided
            if new_customer_name:
                update_data.update({"customer_name": new_customer_name, "customer": new_customer_name})
            if new_customer_email:
                update_data.update({"customer_email": new_customer_email, "email": new_customer_email})
            if new_customer_address:
                update_data.update({"customer_address": new_customer_address, "address": new_customer_address})
            if new_payment_mode:
                update_data.update({"payment_mode": new_payment_mode, "payment": new_payment_mode})
            
            # Apply updates
            for col_idx, header in enumerate(orders_headers):
                clean_header = header.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
                
                for update_key, update_value in update_data.items():
                    if update_value and (update_key in clean_header or clean_header in update_key):
                        col_letter = chr(65 + col_idx)
                        range_name = f"{orders_config['worksheet_name']}!{col_letter}{order_row_index}"
                        
                        service.spreadsheets().values().update(
                            spreadsheetId=orders_config["workbook_id"],
                            range=range_name,
                            valueInputOption="RAW",
                            body={"values": [[update_value]]}
                        ).execute()
                        
                        updates_applied.append(f"{header}: {update_value}")
                        print(f"[DEBUG] Updated {header}: {update_value}")
                        break
            
            return json.dumps({
                "success": True,
                "message": f"Multiple products order {order_id} updated successfully",
                "order_id": order_id,
                "products_changed": True,
                "old_products": f"{len(current_products)} items",
                "new_products": f"{len(validated_new_products)} items", 
                "updates_applied": updates_applied,
                "order_summary": f"""
📋 MULTIPLE PRODUCTS ORDER UPDATED!

🆔 Order ID: {order_id}
📦 Products: {current_products_str} → {new_products_str}
🔢 Quantities: {current_quantities_str} → {new_quantities_str}
💰 New Total: PKR {total_new_amount:,.0f}
👤 Customer: {new_customer_name if new_customer_name else 'unchanged'}

✅ Order updated and inventory synchronized for all products!"""
            })
        
        else:
            # Only customer info updates (no product changes)
            update_data = {}
            if new_customer_name:
                update_data.update({"customer_name": new_customer_name, "customer": new_customer_name})
            if new_customer_email:
                update_data.update({"customer_email": new_customer_email, "email": new_customer_email})
            if new_customer_address:
                update_data.update({"customer_address": new_customer_address, "address": new_customer_address})
            if new_payment_mode:
                update_data.update({"payment_mode": new_payment_mode, "payment": new_payment_mode})
            
            # Apply customer updates
            orders_headers = orders_data["headers"]
            updates_applied = []
            
            for col_idx, header in enumerate(orders_headers):
                clean_header = header.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
                
                for update_key, update_value in update_data.items():
                    if update_value and (update_key in clean_header or clean_header in update_key):
                        col_letter = chr(65 + col_idx)
                        range_name = f"{orders_config['worksheet_name']}!{col_letter}{order_row_index}"
                        
                        service.spreadsheets().values().update(
                            spreadsheetId=orders_config["workbook_id"],
                            range=range_name,
                            valueInputOption="RAW",
                            body={"values": [[update_value]]}
                        ).execute()
                        
                        updates_applied.append(f"{header}: {update_value}")
                        break
            
            return json.dumps({
                "success": True,
                "message": f"Order {order_id} customer information updated",
                "order_id": order_id,
                "products_changed": False,
                "updates_applied": updates_applied
            })
        
    except Exception as e:
        logger.error(f"Multiple products order update failed: {e}")
        return json.dumps({
            "success": False,
            "error": "update_failed",
            "details": str(e)
        })

@mcp.tool()
def cancel_multiple_products_order_tool(order_id: str) -> str:
    """
    Cancel an existing multiple products order by ORDER ID and restore ALL products inventory.
    - Marks order status as 'Cancelled' instead of deleting
    - Restores full quantities for ALL products back to inventory
    - Preserves order history for business records
    - Works with any business type (inventory vs service businesses)
    """
    logger.info(f"Cancelling multiple products order: {order_id}")
    
    conn = load_env_connection()
    if not conn:
        return json.dumps({"success": False, "error": "no_connection_configured"})
    
    inventory_config = conn.get("inventory")
    orders_config = conn.get("orders")
    refresh_token = conn.get("refresh_token")
    
    if not all([inventory_config, orders_config, refresh_token]):
        return json.dumps({"success": False, "error": "missing_configuration"})
    
    try:
        service = build_sheets_service_from_refresh(refresh_token)
        
        # Step 1: Find the order
        orders_data = get_sheet_data(
            service, 
            orders_config["workbook_id"], 
            orders_config["worksheet_name"],
            conn
        )
        
        order_found = False
        order_row_index = -1
        order_details = {}
        
        for idx, order in enumerate(orders_data["data"]):
            detected_cols = smart_column_detection(order, "all")
            if "id" in detected_cols and detected_cols["id"]["value"] == order_id:
                order_found = True
                order_row_index = idx + 2
                order_details = {
                    "products": detected_cols.get("product_name", {}).get("value", ""),
                    "quantities": detected_cols.get("quantity", {}).get("value", ""),
                    "customer_name": detected_cols.get("customer_name", {}).get("value", ""),
                    "total": detected_cols.get("price", {}).get("value", ""),
                    "status": detected_cols.get("status", {}).get("value", "")
                }
                break
        
        if not order_found:
            return json.dumps({
                "success": False,
                "error": "order_not_found",
                "message": f"Order {order_id} not found"
            })
        
        # Check current status
        current_status = order_details["status"].strip()
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
        
        # Step 2: Parse products to restore
        products_str = order_details["products"]
        quantities_str = order_details["quantities"]
        
        products_to_restore = []
        if products_str and quantities_str:
            product_names = products_str.split(',')
            quantities = quantities_str.split(',')
            
            for i, product_name in enumerate(product_names):
                if i < len(quantities):
                    try:
                        qty = int(quantities[i].strip())
                        products_to_restore.append({
                            "name": product_name.strip(),
                            "quantity": qty
                        })
                    except ValueError:
                        continue
        
        print(f"[DEBUG] Products to restore: {products_to_restore}")
        
        # Step 3: Restore inventory for all products
        if products_to_restore:
            inventory_data = get_sheet_data(
                service, 
                inventory_config["workbook_id"], 
                inventory_config["worksheet_name"],
                conn
            )
            
            restored_products = []
            
            for product_item in products_to_restore:
                product_name = product_item["name"]
                quantity_to_restore = product_item["quantity"]
                
                # Find product in inventory
                for idx, item in enumerate(inventory_data["data"]):
                    detected_cols = smart_column_detection(item, "all")
                    if "product_name" in detected_cols:
                        if product_name.lower() in detected_cols["product_name"]["value"].lower():
                            # Safe integer conversion for cancellation
                            quantity_value = detected_cols.get("quantity", {}).get("value", "0")
                            try:
                                current_stock = int(quantity_value)
                                has_numeric_inventory = True
                            except (ValueError, TypeError):
                                has_numeric_inventory = False
                                print(f"[DEBUG] Non-numeric inventory for cancellation: {product_name}")
                            
                            if has_numeric_inventory:
                                new_stock = current_stock + quantity_to_restore
                                
                                # Update inventory
                                product_row_index = idx + 2
                                quantity_col = None
                                for col_letter, header in enumerate(inventory_data["headers"], start=1):
                                    if any(word in header.lower() for word in ["quantity", "qty", "stock"]):
                                        quantity_col = chr(64 + col_letter)
                                        break
                                
                                if quantity_col:
                                    range_name = f"{inventory_config['worksheet_name']}!{quantity_col}{product_row_index}"
                                    service.spreadsheets().values().update(
                                        spreadsheetId=inventory_config["workbook_id"],
                                        range=range_name,
                                        valueInputOption="RAW",
                                        body={"values": [[str(new_stock)]]}
                                    ).execute()
                                    
                                    restored_products.append(f"{product_name}: +{quantity_to_restore}")
                                    print(f"[DEBUG] Restored inventory: {product_name} {current_stock} → {new_stock}")
                            break
        
        # Step 4: Update order status to 'Cancelled'
        orders_headers = orders_data["headers"]
        status_col = None
        
        for col_idx, header in enumerate(orders_headers):
            if "status" in header.lower():
                status_col = chr(65 + col_idx)
                break
        
        if status_col:
            range_name = f"{orders_config['worksheet_name']}!{status_col}{order_row_index}"
            service.spreadsheets().values().update(
                spreadsheetId=orders_config["workbook_id"],
                range=range_name,
                valueInputOption="RAW",
                body={"values": [["Cancelled"]]}
            ).execute()
            print(f"[DEBUG] Order status updated to 'Cancelled'")
        
        return json.dumps({
            "success": True,
            "message": f"Multiple products order {order_id} cancelled successfully",
            "order_id": order_id,
            "cancelled_details": order_details,
            "products_restored": len(products_to_restore),
            "inventory_restored": len(restored_products) > 0,
            "restored_items": restored_products,
            "order_summary": f"""
❌ MULTIPLE PRODUCTS ORDER CANCELLED!

🆔 Cancelled Order: {order_id}
📦 Products: {products_str}
🔢 Quantities: {quantities_str}
👤 Customer: {order_details['customer_name']}

✅ Order marked as 'Cancelled' and all {len(products_to_restore)} products restored to inventory!
📋 Order preserved for business records."""
        })
        
    except Exception as e:
        logger.error(f"Multiple products order cancellation failed: {e}")
        return json.dumps({
            "success": False,
            "error": "cancellation_failed",
            "details": str(e)
        })

# ========================================
# MARKETING TOOLS FOR POSTER GENERATION
# ========================================

# @mcp.tool()
# def google_sheets_query_tool():
#     # we already have this made above for order management.
#     # we'll use that same tool for marketing as well to get the inventory/product data for correct product name to pass in search_product_tool()

@mcp.tool()
def search_product_tool(product_name: str) -> str:
    """
    Search for the specific product in inventory and return complete details of that row.
    
    Dynamic and flexible approach that:
    - Returns ALL columns from the matched row with their original names
    - Works with any sheet structure and column names
    - Preserves actual column headers from your sheet
    - Provides complete product information for marketing
    
    Example output includes: ItemID, Product Name, Price, Weight, Quantity, Status, Media, Tags, etc.
    """
    logger.info(f"Marketing: Searching for product '{product_name}'")
    
    try:
        # Load connection from environment variables
        conn = load_env_connection()
        if not conn or not conn.get("refresh_token"):
            return json.dumps({
                "success": False,
                "error": "missing_env_config",
                "message": "Environment variables not configured properly"
            })
        
        # Build Google Sheets service
        service = build_sheets_service_from_refresh(conn["refresh_token"])
        
        # Get inventory data
        inventory_data = get_sheet_data(
            service,
            conn["inventory"]["workbook_id"],
            conn["inventory"]["worksheet_name"],
            conn
        )
        
        # Get the original headers for reference
        original_headers = inventory_data.get("headers", [])
        
        # Search for the product
        for item in inventory_data["data"]:
            # item is already a processed dictionary with lowercase keys
            # Find product name using flexible detection
            product_found = False
            matched_product_name = ""
            
            # Check various product name variations in the processed item
            for col_key, col_value in item.items():
                if any(keyword in col_key.lower() for keyword in ["product", "name", "item", "title"]):
                    item_name = str(col_value).strip()
                    if item_name and product_name.lower() in item_name.lower():
                        product_found = True
                        matched_product_name = item_name
                        break
            
            if product_found:
                # Build complete product details with ALL available columns
                complete_product_data = {}
                
                # Create mapping from processed keys back to original headers
                original_to_processed = {}
                processed_to_original = {}
                
                if len(original_headers) <= len(item):
                    for i, header in enumerate(original_headers):
                        processed_key = header.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
                        original_to_processed[header] = processed_key
                        processed_to_original[processed_key] = header
                
                # Add all available data using original column names
                for processed_key, value in item.items():
                    original_key = processed_to_original.get(processed_key, processed_key)
                    complete_product_data[original_key] = value
                
                # Add raw row data for reference (using original headers)
                raw_row_data = complete_product_data.copy()
                
                # Enhanced response with flexible structure
                logger.info(f"Marketing: Found product '{matched_product_name}' with {len(complete_product_data)} columns")
                
                return json.dumps({
                    "success": True,
                    "product": {
                        "matched_name": matched_product_name,
                        "search_query": product_name,
                        "columns_found": len(complete_product_data),
                        "product_data": complete_product_data,
                        "raw_row": raw_row_data,
                        "available_columns": list(complete_product_data.keys())
                    },
                    "sheet_info": {
                        "total_headers": len(original_headers),
                        "headers": original_headers
                    },
                    "message": f"Product '{matched_product_name}' found with complete row data"
                })
        
        # Product not found
        return json.dumps({
            "success": False,
            "error": "product_not_found",
            "message": f"Product '{product_name}' not found in inventory",
            "sheet_info": {
                "total_products": len(inventory_data["data"]),
                "available_headers": original_headers
            }
        })
        
    except Exception as e:
        logger.error(f"Marketing product search failed: {e}")
        return json.dumps({
            "success": False,
            "error": "search_failed",
            "message": str(e)
        })

@mcp.tool()
def prompt_structure_tool(product_details: str, user_prompt: str) -> str:
    """
    Create optimized prompt for poster generation using product details.
    Takes product details and formats them into Gemini-friendly marketing prompt.
    """
    logger.info(f"Marketing: Structuring prompt for poster style")
    
    try:
        # Parse product details
        product_data = json.loads(product_details)
        
        # Handle both full search_product_tool response AND direct product data
        if product_data.get("success") and "product" in product_data:
            # Full search_product_tool response format
            product = product_data.get("product", {}).get("product_data", {})
        else:
            # Direct product data format (what the client is actually sending)
            product = product_data
        
        if not product:
            return json.dumps({
                "success": False,
                "error": "empty_product_data", 
                "message": "No product data found in the provided details"
            })
        
        # Create optimized prompt template for marketing posters
        prompt_template = f"""Create a professional marketing poster by looking at the product details and user prompt below. Make sure you also look at the User Prompt and follow it as well.

Look at the product details below and create a clean, professional marketing poster for that product. Looking at the product details, smartly look for necessary information to create the poster like look for product name, price, features, weight, tags, etc. Anything that should be in the poster.

Create a marketing poster suitable for social media, print, and digital advertising. Include all text elements clearly readable. Make the product the hero of the design.

Design requirements: Modern typography, elegant layout, corporate decent colors (look at the image that you have to decide which colors to use), professional product photography style, clear pricing display, minimalist design elements.

Product details:
{product}

User Prompt:
{user_prompt}"""
        
        logger.info(f"Marketing: Prompt structured successfully for '{product.get('Product Name', 'Unknown Product')}'")
        
        return json.dumps({
            "success": True,
            "prompt": prompt_template,
            "product_name": product.get("Product Name"),
            "has_product_image": bool(product.get("Media")),
            "product_image_url": product.get("Media", ""),
            "message": f"Prompt created for {product.get('Product Name', 'Unknown Product')} Poster Generation"
        })
        
    except json.JSONDecodeError:
        return json.dumps({
            "success": False,
            "error": "invalid_json",
            "message": "Product details must be valid JSON"
        })
    except Exception as e:
        logger.error(f"Marketing prompt structuring failed: {e}")
        return json.dumps({
            "success": False,
            "error": "prompt_creation_failed",
            "message": str(e)
        })

@mcp.tool()
def generate_images_tool(prompt: str, product_image_url: str = "", output_format: str = "base64") -> str:
    """
    Generate marketing poster using Gemini 2.5 Flash Image API.
    Can work with prompt-only or prompt + existing product image from Google Sheets.
    
    Images are ALWAYS saved as PNG files to avoid long base64 strings in responses.
    Returns filenames instead of base64 data for better performance and usability.
    
    Parameters:
    - prompt: Marketing prompt for poster generation
    - product_image_url: Optional product image URL from Media column
    - output_format: "base64" saves additional .txt file with base64 data, "file" saves PNG only
    
    Returns:
    - generated_images: List of PNG filenames created
    - base64_files: List of .txt files with base64 data (if output_format="base64")
    """
    logger.info(f"Marketing: Generating poster image with Gemini API")
    
    try:
        # Get Gemini API key from environment
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            return json.dumps({
                "success": False,
                "error": "missing_gemini_api_key",
                "message": "GEMINI_API_KEY not found in environment variables. Please add it to .env file."
            })
        
        # Try to import and use Gemini API
        try:
            from google import genai
            from PIL import Image
            
            # Initialize Gemini client
            client = genai.Client(api_key=gemini_api_key)
            
            # Enhance prompt to request social media caption alongside image
            enhanced_prompt = f"""{prompt}

CRITICAL INSTRUCTION FOR CAPTION:
After creating the poster image, provide an Instagram/social media caption for this product.

STRICT RULES FOR CAPTION:
1. Start DIRECTLY with the caption text - NO introductory phrases
2. DO NOT include prefixes like "Here's a caption:", "Caption:", "**Caption:**", etc.
3. DO NOT include separators like "---"
4. Just write the actual caption text that would be posted
5. Include relevant hashtags at the end
6. Keep it engaging, concise, and ready to copy-paste

Example of what to provide:
✨ Discover amazing skin! This product will transform your routine...
#Beauty #Skincare #Glow

(Just like that - nothing before the actual caption)"""
            
            # Prepare content for generation
            contents = [enhanced_prompt]
            
            # If product image URL is provided, fetch and include it
            product_image_status = "no_image"
            if product_image_url:
                try:
                    logger.info(f"Marketing: Fetching product image from {product_image_url}")
                    response = requests.get(product_image_url, timeout=10)
                    if response.status_code == 200:
                        image = Image.open(BytesIO(response.content))
                        contents.append(image)
                        product_image_status = "image_added"
                        logger.info("Marketing: Product image successfully added to generation")
                    else:
                        product_image_status = f"fetch_failed_status_{response.status_code}"
                        logger.warning(f"Marketing: Could not fetch product image, status: {response.status_code}")
                except Exception as e:
                    product_image_status = f"fetch_error_{str(e)}"
                    logger.warning(f"Marketing: Product image fetch failed: {e}")
                    # Continue without image
            
            # Generate poster using Gemini Image Generation Model
            logger.info("Marketing: Calling Gemini API for image generation")
            
            # Get model name from environment variables
            primary_model = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-image")
            primary_model_error = None
            
            # Try different image generation models (primary first, then fallbacks)
            image_models = [
                primary_model,                  # Model from .env
            ]
            
            response = None
            model_used = None
            
            for model in image_models:
                try:
                    logger.info(f"Marketing: Trying model {model}")
                    response = client.models.generate_content(
                        model=model,
                        contents=contents,
                    )
                    model_used = model
                    logger.info(f"Marketing: Successfully used model {model}")
                    break
                except Exception as model_error:
                    logger.warning(f"Marketing: Model {model} failed: {model_error}")
                    primary_model_error = str(model_error)
                    logger.error(f"Marketing: Model {primary_model} failed: {model_error}")
                    
                    # Check if it's a quota issue and provide helpful feedback
                    if "RESOURCE_EXHAUSTED" in str(model_error) or "quota" in str(model_error).lower():
                        logger.error("Marketing: ⚠️ QUOTA EXHAUSTED - Please upgrade to paid tier for image generation!")
                    break
            
            if not response:
                return json.dumps({
                    "success": False,
                    "error": "image_generation_failed",
                    "message": f"Image generation failed with {primary_model}. Please check your API quota and upgrade to paid tier if needed.",
                    "primary_model_error": primary_model_error,
                    "quota_exhausted": "RESOURCE_EXHAUSTED" in (primary_model_error or "")
                })
            
            # Process response
            generated_images = []
            base64_files_created = []
            text_response = ""
            
            for part in response.candidates[0].content.parts:
                if part.text is not None:
                    text_response = part.text
                    logger.info("Marketing: Received text description from Gemini")
                elif part.inline_data is not None:
                    # Always save image to file to avoid long base64 strings in response
                    image = Image.open(BytesIO(part.inline_data.data))
                    
                    # Generate unique filename with timestamp
                    timestamp = int(time.time())
                    filename = f"poster_{timestamp}.png"
                    
                    # Save the image file
                    image.save(filename)
                    generated_images.append(filename)
                    logger.info(f"Marketing: Image saved as {filename}")
                    
                    # If user specifically requested base64, save to external file like view_poster.py
                    if output_format == "base64":
                        # Save base64 data to external file for viewing later if needed
                        buffered = BytesIO()
                        image.save(buffered, format="PNG")
                        img_base64 = base64.b64encode(buffered.getvalue()).decode()
                        base64_data = f"data:image/png;base64,{img_base64}"
                        
                        # Save base64 to external file like poster_data.txt
                        base64_filename = f"poster_base64_{timestamp}.txt"
                        with open(base64_filename, 'w') as f:
                            f.write(base64_data)
                        base64_files_created.append(base64_filename)
                        logger.info(f"Marketing: Base64 data saved to {base64_filename}")
                    
                    # Always return the filename instead of base64 string
            
            logger.info("Marketing: Poster generated successfully with Gemini API")
            
            # Generate social media caption from AI response or create fallback
            # Clean up the caption by removing any instructional prefixes
            raw_caption = text_response.strip() if text_response else ""
            
            # Use regex to remove any instruction text before the actual caption
            import re
            
            # Step 1: Remove everything up to the last "Caption:" or similar instruction
            social_media_caption = re.sub(
                r'^.*?(?:\*\*)?(?:caption|instagram|social\s+media):?\*\*?\s*\n*',
                '',
                raw_caption,
                flags=re.IGNORECASE
            ).strip()
            
            # Step 2: Remove any markdown separators
            social_media_caption = re.sub(r'^-+\s*\n*', '', social_media_caption).strip()
            
            # Step 3: Remove leading/trailing markdown bold markers if present
            social_media_caption = re.sub(r'^\*\*|\*\*$', '', social_media_caption).strip()
            
            # Fallback if no caption generated
            if not social_media_caption or len(social_media_caption) < 10:
                social_media_caption = "Check out this amazing product! 🌟 #NewArrival #MustHave"
            
            return json.dumps({
                "success": True,
                "generated_images": generated_images,
                "generated_files": generated_images,  # Always contains PNG filenames now
                "base64_files": base64_files_created,  # Contains base64 data files if requested
                "caption": social_media_caption,  # AI-generated social media caption with hashtags
                "description": text_response or "Marketing poster generated successfully",
                "prompt_used": prompt,
                "has_product_image": bool(product_image_url),
                "product_image_url": product_image_url,
                "product_image_status": product_image_status,
                "api_status": "real_gemini_api",
                "model_used": model_used or primary_model,
                "primary_model_requested": primary_model,
                "primary_model_error": None,
                "fallback_used": False,
                "quota_exhausted": False,
                "is_text_only_response": len(generated_images) == 0 and text_response is not None,
                "image_handling": "saved_as_files",
                "output_format_requested": output_format,
                "has_social_caption": bool(text_response),
                "message": f"✅ Poster generated successfully using {model_used or primary_model}. Images saved as: {', '.join(generated_images)}"
            })
            
        except ImportError:
            # Fallback if Gemini library not installed
            logger.warning("Marketing: Gemini library not installed, using mock response")
            return json.dumps({
                "success": False,
                "error": "gemini_library_missing",
                "message": "Google Gemini library not installed. Install with: pip install google-genai",
                "api_status": "library_missing"
            })
        
        except Exception as api_error:
            logger.error(f"Marketing: Gemini API call failed: {api_error}")
            return json.dumps({
                "success": False,
                "error": "gemini_api_error",
                "message": f"Gemini API error: {str(api_error)}",
                "api_status": "api_error"
            })
        
    except Exception as e:
        logger.error(f"Marketing image generation failed: {e}")
        return json.dumps({
            "success": False,
            "error": "generation_failed",
            "message": str(e)
        })

@mcp.tool()
def upload_poster_to_imagekit_tool(
    image_filename: str,
    tenant_id: str = None,
    caption: str = ""
) -> str:
    """
    Upload generated poster to ImageKit CDN and save metadata to Neon Postgres database.
    
    Production-ready: Reads file, uploads to cloud, saves to database, deletes local file.
    
    Parameters:
    - image_filename: Local PNG filename from generate_images_tool (e.g., "poster_123.png")
    - tenant_id: User/session identifier (auto-generated if not provided)
    - caption: Social media caption from generate_images_tool
    
    Returns: ImageKit CDN URL and database confirmation
    
    Example:
    upload_poster_to_imagekit_tool(
        image_filename="poster_1762793854.png",
        tenant_id="user_shamoon",
        caption="Amazing skin! 🌿 #AloeVera"
    )
    """
    logger.info(f"Marketing: Uploading poster to ImageKit: {image_filename}")
    
    try:
        # Step 1: Auto-generate tenant_id if not provided
        if not tenant_id or tenant_id.strip() == "":
            tenant_id = f"user_{uuid.uuid4().hex[:12]}"
            logger.info(f"Marketing: Auto-generated tenant_id: {tenant_id}")
        
        # Step 2: Check if local file exists
        if not os.path.exists(image_filename):
            return json.dumps({
                "success": False,
                "error": "file_not_found",
                "message": f"Image file '{image_filename}' not found locally"
            })
        
        # Step 3: Read file into memory and encode as base64
        logger.info(f"Marketing: Reading file into memory: {image_filename}")
        with open(image_filename, 'rb') as file:
            file_content = file.read()
        
        # Encode to base64 string for ImageKit upload
        import base64
        file_base64 = base64.b64encode(file_content).decode('utf-8')
        
        # Step 4: Initialize ImageKit client
        imagekit_private_key = os.getenv("IMAGEKIT_PRIVATE_KEY")
        imagekit_public_key = os.getenv("IMAGEKIT_PUBLIC_KEY")
        imagekit_url_endpoint = os.getenv("IMAGEKIT_URL_ENDPOINT")
        
        if not all([imagekit_private_key, imagekit_public_key, imagekit_url_endpoint]):
            return json.dumps({
                "success": False,
                "error": "missing_imagekit_config",
                "message": "ImageKit credentials not found in environment variables. Check IMAGEKIT_PRIVATE_KEY, IMAGEKIT_PUBLIC_KEY, IMAGEKIT_URL_ENDPOINT"
            })
        
        imagekit = ImageKit(
            private_key=imagekit_private_key,
            public_key=imagekit_public_key,
            url_endpoint=imagekit_url_endpoint
        )
        
        # Step 5: Upload to ImageKit
        logger.info(f"Marketing: Uploading to ImageKit CDN with folder: /posters/{tenant_id}/")
        
        # Import UploadFileRequestOptions from ImageKit SDK
        from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
        
        # Create proper options object as per ImageKit SDK documentation
        upload_options = UploadFileRequestOptions(
            folder=f"/posters/{tenant_id}/",
            use_unique_file_name=True,
            tags=["marketing", "poster", "auto-generated"]  # List of strings
        )
        
        upload_result = imagekit.upload_file(
            file=file_base64,  # Use base64-encoded string
            file_name=image_filename,
            options=upload_options
        )
        
        # Handle response (ImageKit SDK returns UploadFileResult object)
        imagekit_url = upload_result.url
        imagekit_file_id = upload_result.file_id
        
        logger.info(f"Marketing: Successfully uploaded to ImageKit: {imagekit_url}")
        
        # Step 6: Ensure database table exists and get connection
        conn = ensure_poster_table_exists()
        cursor = conn.cursor()
        
        # Step 7: Save metadata to database
        logger.info(f"Marketing: Saving metadata to Neon Postgres database")
        
        cursor.execute("""
            INSERT INTO poster_generations 
            (tenant_id, image_url, image_caption)
            VALUES (%s, %s, %s)
        """, (tenant_id, imagekit_url, caption))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Marketing: Database record saved successfully")
        
        # Step 8: Delete local file (production-ready, stateless)
        local_file_deleted = False
        try:
            os.remove(image_filename)
            local_file_deleted = True
            logger.info(f"Marketing: Deleted local file: {image_filename}")
        except Exception as delete_error:
            logger.warning(f"Marketing: Could not delete local file {image_filename}: {delete_error}")
        
        # Step 9: Return success response
        return json.dumps({
            "success": True,
            "imagekit_url": imagekit_url,
            "imagekit_file_id": imagekit_file_id,
            "tenant_id": tenant_id,
            "caption": caption,
            "local_file_deleted": local_file_deleted,
            "folder": f"/posters/{tenant_id}/",
            "message": f"✅ Poster uploaded to ImageKit and saved to database. CDN URL ready!"
        })
        
    except Exception as e:
        logger.error(f"Marketing: Poster upload failed: {e}")
        return json.dumps({
            "success": False,
            "error": "upload_failed",
            "message": f"Failed to upload poster: {str(e)}"
        })

# ========================================
# EMAIL MARKETING TOOLS
# ========================================

# @mcp.tool()
# def google_sheets_query_tool():
#     # we already have this made above for order management.
#     # we'll use that same tool for email marketing as well to get the inventory/product data for correct product name, product price and image url to pass in email_content_tool()

@mcp.tool()
def email_content_tool(product_name: str, product_price: str, image_url: str, shop_link: str = "https://your-shop-link.com", company_name: str = "Skincare Business") -> str:
    """
    Generates a dark-style, dynamic HTML email campaign for a single product.
    This is the main tool for creating email content to send for approval and to customers.

    Args:
        product_name (str): The name of the product (e.g., "Night Repair Serum").
        product_price (str): The price of the product (e.g., "Rs. 1500").
        image_url (str): The publicly accessible URL of the product image.
        shop_link (str): The URL for the "Shop Now" button. Defaults to placeholder.
        company_name (str): The name of the company for the footer. Defaults to "Skincare Business".

    Returns:
        str: JSON response with email_content and email_subject.
        
        IMPORTANT FOR AI AGENTS: The response is a JSON string. To use the email_content 
        with get_email_design_approval_tool(), you MUST parse this JSON response first:
        
        1. Parse the JSON: result = json.loads(response)
        2. Extract HTML: html = result["email_content"]
        3. Pass to next tool: get_email_design_approval_tool(email_content=html, ...)
        
        DO NOT copy-paste the raw response text! The HTML contains actual newlines that 
        appear as \\n in the JSON string. You must parse the JSON to get the real HTML.
    """
    logger.info(f"Email Marketing: Generating email for {product_name}")
    
    try:
        # HTML Template with placeholders
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Dynamic Skincare Campaign</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">

    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed;">
        <tr>
            <td align="center" style="padding: 20px 0;">

                <table border="0" cellpadding="0" cellspacing="0" width="600" style="border-collapse: collapse; background-color: #1a1a1a; border-radius: 8px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);">
                    
                    <tr>
                        <td align="center" style="padding: 0;">
                            <img src="IMAGE_URL_PLACEHOLDER" alt="Product Image: PRODUCT_NAME_PLACEHOLDER" width="600" style="display: block; width: 100%; max-width: 600px; height: auto; border-top-left-radius: 8px; border-top-right-radius: 8px;">
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 30px 40px; color: #ffffff; text-align: center;">
                            
                            <h1 style="margin-top: 0; margin-bottom: 20px; font-size: 24px; color: #ffebf0;">
                                Introducing the amazing PRODUCT_NAME_PLACEHOLDER!
                            </h1>

                            <p style="margin-bottom: 15px; font-size: 16px; line-height: 1.6;">
                                Take care of your Skin because it's worth it! Our products help you get the perfect skin!
                            </p>
                            
                            <p style="margin-bottom: 25px; font-size: 18px; line-height: 1.6;">
                                Just for <span style="font-weight: bold; color: #ff99aa;">PRICE_PLACEHOLDER</span>
                            </p>

                            <p style="margin-bottom: 30px; font-size: 20px; font-style: italic; color: #cccccc;">
                                Get Soft Skin in minutes with PRODUCT_NAME_PLACEHOLDER!
                            </p>

                            <table border="0" cellpadding="0" cellspacing="0" style="margin: 0 auto;">
                                <tr>
                                    <td align="center" style="border-radius: 5px; background-color: #ff99aa;">
                                        <a href="SHOP_LINK_PLACEHOLDER" target="_blank" style="font-size: 16px; font-family: Arial, sans-serif; color: #1a1a1a; text-decoration: none; padding: 12px 25px; border: 1px solid #ff99aa; display: inline-block; border-radius: 5px; font-weight: bold;">
                                            Shop Now
                                        </a>
                                    </td>
                                </tr>
                            </table>

                        </td>
                    </tr>

                    <tr>
                        <td align="center" style="padding: 10px; background-color: #0d0d0d; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
                            <p style="margin: 0; font-size: 12px; color: #777777;">
                                &copy; 2025 COMPANY_NAME_PLACEHOLDER
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>

</body>
</html>
"""
        
        # Substitution Logic - Replace placeholders with actual values
        final_html = html_template.replace("PRODUCT_NAME_PLACEHOLDER", product_name)
        final_html = final_html.replace("PRICE_PLACEHOLDER", product_price)
        final_html = final_html.replace("IMAGE_URL_PLACEHOLDER", image_url)
        final_html = final_html.replace("SHOP_LINK_PLACEHOLDER", shop_link)
        final_html = final_html.replace("COMPANY_NAME_PLACEHOLDER", company_name)
        
        # Generate subject line
        subject_line = f"✨ Introducing {product_name} - Just for {product_price}!"
        
        logger.info(f"Email Marketing: Email content generated for {product_name}")
        
        # Create response with clear instructions for AI agents
        response = {
            "success": True,
            "email_content": final_html,
            "email_subject": subject_line,
            "product_featured": product_name,
            "ready_for_approval": True,
            "message": f"Email content created successfully for {product_name}",
            "next_step_instructions": "To send approval email, call get_email_design_approval_tool() with the email_content and email_subject from this response. IMPORTANT: Parse this JSON first to extract the actual HTML content - do not pass the raw JSON string!"
        }
        
        return json.dumps(response)
        
    except Exception as e:
        logger.error(f"Email Marketing: Email generation failed: {e}")
        return json.dumps({
            "success": False,
            "error": "email_generation_failed",
            "message": str(e)
        })

@mcp.tool()
def get_email_design_approval_tool(email_content: str, subject_line: str, owner_email: str, approval_message: str = "") -> str:
    """
    Send email preview to business owner for approval.
    Sends the actual campaign email directly (no wrapper to avoid HTML escaping issues).
    Adds approval instructions at the top.
    
    Parameters:
    - email_content: HTML email template from email_content_tool
    - subject_line: Email subject
    - owner_email: Business owner's email for approval
    - approval_message: Custom message for owner
    """
    logger.info(f"Email Marketing: Sending approval email to {owner_email}")
    
    # DEBUG: Check what we're receiving
    logger.info(f"Email Marketing: Received email_content length: {len(email_content)}")
    logger.info(f"Email Marketing: First 100 chars: {email_content[:100]}")
    logger.info(f"Email Marketing: Contains literal backslash-n: {'\\n' in email_content}")
    logger.info(f"Email Marketing: Contains real newlines: {chr(10) in email_content[:100]}")
    
    # AUTO-FIX: Detect and fix escaped HTML
    # Check if we have literal "\n" text (which appears as backslash-n in the string)
    # This happens when the MCP client passes double-escaped JSON
    if '\\n' in email_content:
        # Count how many literal \n vs real newlines in first 200 chars
        sample = email_content[:200]
        has_escaped = sample.count('\\n') > 0
        has_real_newlines = sample.count('\n') > 0
        
        # If we have more escaped than real newlines, it's escaped HTML
        if has_escaped and not has_real_newlines:
            logger.warning("⚠️ Email Marketing: Received ESCAPED HTML! Auto-fixing...")
            logger.info(f"Before fix sample: {repr(email_content[:80])}")
            
            # Replace escaped characters with real ones
            email_content = email_content.replace('\\n', '\n')
            email_content = email_content.replace('\\t', '\t')
            email_content = email_content.replace('\\"', '"')
            email_content = email_content.replace("\\'", "'")
            
            logger.info(f"After fix sample: {repr(email_content[:80])}")
            logger.info("✅ HTML auto-fixed successfully!")
    
    try:
        # Load environment variables
        load_dotenv()
        refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        
        if not refresh_token:
            return {
                "success": False,
                "error": "missing_google_credentials",
                "message": "Google refresh token not found in environment variables"
            }
        
        # Create approval email by adding instructions banner ABOVE the campaign HTML
        # This way we avoid HTML-in-HTML escaping issues
        approval_subject = f"📧 APPROVAL NEEDED: {subject_line}"
        
        # Extract BODY content from campaign HTML (not the full HTML doc)
        # This prevents nested HTML documents which cause the inner HTML to be treated as text
        import re
        
        # Extract content between <body> and </body> tags
        body_match = re.search(r'<body[^>]*>(.*?)</body>', email_content, re.DOTALL | re.IGNORECASE)
        if body_match:
            campaign_body_content = body_match.group(1).strip()
        else:
            # Fallback: if no body tags found, use the content as-is
            campaign_body_content = email_content
        
        # Create a SINGLE, SIMPLE HTML document (no nesting, no f-strings with HTML inside)
        # Build it piece by piece to avoid any escaping issues
        approval_html_parts = []
        
        # Part 1: HTML opening and approval header
        approval_html_parts.append("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background-color:#f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#3498db;padding:20px;">
        <tr>
            <td align="center" style="color:white;">
                <h2 style="margin:0 0 10px 0;">EMAIL CAMPAIGN APPROVAL REQUIRED</h2>
                <p style="margin:5px 0;">Subject: """)
        
        approval_html_parts.append(subject_line)
        approval_html_parts.append("""</p>""")
        
        if approval_message:
            approval_html_parts.append("""<p style="margin:10px 0;background-color:#ffc107;color:#000;padding:10px;border-radius:5px;">Note: """)
            approval_html_parts.append(approval_message)
            approval_html_parts.append("""</p>""")
        
        approval_html_parts.append("""
                <p style="margin:15px 0 5px 0;font-size:16px;">TO APPROVE: Reply "APPROVED" | TO CANCEL: Reply "CANCEL"</p>
            </td>
        </tr>
    </table>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#27ae60;padding:15px;">
        <tr>
            <td align="center" style="color:white;font-size:18px;font-weight:bold;">
                CAMPAIGN EMAIL PREVIEW BELOW
            </td>
        </tr>
    </table>
    
    <!-- Campaign content starts here -->
""")
        
        # Part 2: Campaign body content (no escaping, direct insertion)
        approval_html_parts.append(campaign_body_content)
        
        # Part 3: Closing sections
        approval_html_parts.append("""
    <!-- Campaign content ends here -->
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#27ae60;padding:15px;">
        <tr>
            <td align="center" style="color:white;font-size:18px;font-weight:bold;">
                CAMPAIGN EMAIL PREVIEW ABOVE
            </td>
        </tr>
    </table>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#e8f8f5;padding:20px;">
        <tr>
            <td align="center" style="color:#27ae60;font-weight:bold;font-size:16px;">
                Ready to send? Reply to this email with "APPROVED" or "CANCEL"!
            </td>
        </tr>
    </table>
</body>
</html>""")
        
        # Join all parts into final HTML (no f-string, no variable interpolation that could escape HTML)
        final_approval_html = ''.join(approval_html_parts)
        
        # Try Gmail API first, fallback to SMTP
        try:
            gmail_service = build_gmail_service_from_refresh(refresh_token)
            send_method = "gmail_api"
        except Exception as gmail_error:
            logger.warning(f"Gmail API not available, using SMTP: {gmail_error}")
            send_method = "smtp"
        
        if send_method == "smtp":
            smtp_result = send_smtp_email(
                to_email=owner_email,
                from_email=owner_email,
                subject=approval_subject,
                html_content=final_approval_html
            )
            
            if smtp_result:
                logger.info("Email Marketing: Approval email sent via SMTP")
                return {
                    "success": True,
                    "approval_email_sent": True,
                    "sent_to": owner_email,
                    "send_method": "smtp",
                    "message": f"Email preview sent to {owner_email} for approval via SMTP"
                }
            else:
                raise Exception("SMTP sending failed")
        
        # Gmail API sending
        msg = create_gmail_message(
            sender=owner_email,
            to=owner_email,
            subject=approval_subject,
            html_content=final_approval_html
        )
        
        result = gmail_service.users().messages().send(
            userId='me',
            body=msg
        ).execute()
        
        logger.info(f"Email Marketing: Approval email sent, message ID: {result['id']}")
        
        return {
            "success": True,
            "approval_email_sent": True,
            "sent_to": owner_email,
            "gmail_message_id": result['id'],
            "send_method": "gmail_api",
            "message": f"Email preview sent to {owner_email} for approval"
        }
        
    except Exception as e:
        logger.error(f"Email Marketing: Approval email failed: {e}")
        return {
            "success": False,
            "error": "approval_email_failed",
            "message": str(e)
        }

@mcp.tool()
def send_emails_tool(approved_email_content: str, subject_line: str, sender_email: str = "shamoonahmed.ai@gmail.com", campaign_name: str = "", test_mode: bool = False) -> str:
    """
    Send approved marketing emails to all customers from orders sheet
    
    Parameters:
    - approved_email_content: Final approved HTML email content
    - subject_line: Email subject line
    - sender_email: Email address to send from
    - campaign_name: Campaign name for tracking
    - test_mode: If true, send only to sender email for testing
    """
    logger.info(f"Email Marketing: Starting email campaign '{campaign_name}'")
    
    # AUTO-FIX: Detect and fix escaped HTML (same logic as approval tool)
    if '\\n' in approved_email_content:
        sample = approved_email_content[:200]
        has_escaped = sample.count('\\n') > 0
        has_real_newlines = sample.count('\n') > 0
        
        if has_escaped and not has_real_newlines:
            logger.warning("⚠️ Email Marketing: Received ESCAPED HTML in send_emails_tool! Auto-fixing...")
            approved_email_content = approved_email_content.replace('\\n', '\n')
            approved_email_content = approved_email_content.replace('\\t', '\t')
            approved_email_content = approved_email_content.replace('\\"', '"')
            approved_email_content = approved_email_content.replace("\\'", "'")
            logger.info("✅ HTML auto-fixed successfully!")
    
    try:
        # Load connection data
        conn = load_env_connection()
        if not conn or not conn.get("refresh_token"):
            return {
                "success": False,
                "error": "missing_connection",
                "message": "Google connection not configured"
            }
        
        # Build services
        sheets_service = build_sheets_service_from_refresh(conn["refresh_token"])
        
        # Try Gmail API first, fallback to SMTP (same as approval tool)
        try:
            gmail_service = build_gmail_service_from_refresh(conn["refresh_token"])
            send_method = "gmail_api"
        except Exception as gmail_error:
            logger.warning(f"Gmail API not available: {gmail_error}")
            logger.info("Using SMTP for email sending")
            send_method = "smtp"
        
        if test_mode:
            # Test mode: send only to sender email using SMTP
            try:
                if send_method == "smtp":
                    # Use SMTP for test email
                    smtp_result = send_smtp_email(
                        to_email=sender_email,
                        from_email=sender_email,
                        subject=f"[TEST] {subject_line}",
                        html_content=approved_email_content
                    )
                    
                    if smtp_result:
                        return {
                            "success": True,
                            "test_mode": True,
                            "emails_sent": 1,
                            "sent_to": [sender_email],
                            "campaign_id": f"TEST_{int(time.time())}",
                            "send_method": "smtp",
                            "message": f"Test email sent to {sender_email} successfully via SMTP"
                        }
                    else:
                        raise Exception("SMTP test sending failed")
                        
                else:
                    # Use Gmail API for test email
                    msg = create_gmail_message(
                        sender=sender_email,
                        to=sender_email,
                        subject=f"[TEST] {subject_line}",
                        html_content=approved_email_content
                    )
                    
                    result = gmail_service.users().messages().send(
                        userId='me',
                        body=msg
                    ).execute()
                    
                    return {
                        "success": True,
                        "test_mode": True,
                        "emails_sent": 1,
                        "sent_to": [sender_email],
                        "campaign_id": f"TEST_{int(time.time())}",
                        "send_method": "gmail_api",
                        "message": f"Test email sent to {sender_email} successfully via Gmail API"
                    }
                
            except Exception as test_error:
                return {
                    "success": False,
                    "error": "test_send_failed",
                    "message": f"Test email failed: {str(test_error)}"
                }
        
        # Get customer emails from orders sheet
        orders_data = get_sheet_data(
            sheets_service,
            conn["orders"]["workbook_id"],
            conn["orders"]["worksheet_name"],
            conn
        )
        
        # Extract unique customer emails from email column only
        customer_emails = set()
        for order in orders_data["data"]:
            # Try direct field access first (raw field names)
            for field_name in ["customer_email", "email", "customer email", "Email", "Customer Email"]:
                if field_name in order:
                    email = order[field_name]
                    if email and email.strip():  # Just check if it exists and not empty
                        customer_emails.add(email.strip())
                        logger.info(f"Email Marketing: Found email '{email}' in field '{field_name}'")
                        break
            
            # Fallback to smart column detection if direct access didn't work
            if not customer_emails:
                detected_cols = smart_column_detection(order, "all")
                for field_name in ["customer_email", "email", "customer email", "Email", "Customer Email"]:
                    if field_name in detected_cols:
                        email = detected_cols[field_name]["value"]
                        if email and email.strip():
                            customer_emails.add(email.strip())
                            logger.info(f"Email Marketing: Found email '{email}' via smart detection in '{field_name}'")
                            break
        
        if not customer_emails:
            return {
                "success": False,
                "error": "no_customer_emails",
                "message": "No customer emails found in orders sheet"
            }
        
        # Send emails to all customers
        campaign_id = f"CAMP_{int(time.time())}"
        sent_emails = []
        failed_emails = []
        
        for customer_email in customer_emails:
            try:
                if send_method == "smtp":
                    # Use SMTP for sending
                    success = send_smtp_email(
                        to_email=customer_email,
                        from_email=sender_email,
                        subject=subject_line,
                        html_content=approved_email_content
                    )
                    
                    if success:
                        sent_emails.append(customer_email)
                        logger.info(f"Email Marketing: Sent via SMTP to {customer_email}")
                    else:
                        failed_emails.append(customer_email)
                        logger.error(f"Email Marketing: Failed SMTP to {customer_email}")
                else:
                    # Use Gmail API for sending
                    msg = create_gmail_message(
                        sender=sender_email,
                        to=customer_email,
                        subject=subject_line,
                        html_content=approved_email_content
                    )
                    
                    result = gmail_service.users().messages().send(
                        userId='me',
                        body=msg
                    ).execute()
                    
                    sent_emails.append(customer_email)
                    logger.info(f"Email Marketing: Sent via Gmail API to {customer_email}")
                
                # Small delay to avoid rate limits
                time.sleep(0.1)
                
            except Exception as send_error:
                # Try SMTP fallback if Gmail API fails
                if send_method != "smtp":
                    try:
                        logger.info(f"Gmail API failed for {customer_email}, trying SMTP fallback...")
                        success = send_smtp_email(
                            to_email=customer_email,
                            from_email=sender_email,
                            subject=subject_line,
                            html_content=approved_email_content
                        )
                        
                        if success:
                            sent_emails.append(customer_email)
                            logger.info(f"Email Marketing: Sent via SMTP fallback to {customer_email}")
                        else:
                            failed_emails.append(customer_email)
                            logger.error(f"Email Marketing: SMTP fallback also failed for {customer_email}")
                    except Exception as smtp_error:
                        failed_emails.append(customer_email)
                        logger.error(f"Email Marketing: Both Gmail API and SMTP failed for {customer_email}: {smtp_error}")
                else:
                    failed_emails.append(customer_email)
                    logger.error(f"Email Marketing: Failed to send to {customer_email}: {send_error}")
        
        logger.info(f"Email Marketing: Campaign complete. Sent: {len(sent_emails)}, Failed: {len(failed_emails)}")
        
        return {
            "success": True,
            "emails_sent": len(sent_emails),
            "failed_emails": len(failed_emails),
            "campaign_id": campaign_id,
            "campaign_name": campaign_name or "Email Campaign",
            "sent_to_customers": sent_emails[:10],  # Show first 10 for privacy
            "failed_addresses": failed_emails,
            "total_customers": len(customer_emails),
            "delivery_status": "completed",
            "message": f"Successfully sent {subject_line} to {len(sent_emails)} customers!"
        }
        
    except Exception as e:
        logger.error(f"Email Marketing: Campaign failed: {e}")
        return {
            "success": False,
            "error": "campaign_failed",
            "message": str(e)
        }

def build_gmail_service_from_refresh(refresh_token):
    """Build Gmail service using refresh token"""
    try:
        from googleapiclient.discovery import build
        
        # Use existing Google OAuth credentials
        creds = build_google_credentials_from_refresh(refresh_token)
        service = build('gmail', 'v1', credentials=creds)
        return service
        
    except Exception as e:
        logger.error(f"Failed to build Gmail service: {e}")
        raise

def create_gmail_message(sender, to, subject, html_content):
    """Create Gmail API message with HTML-only content (force HTML rendering)"""
    import base64
    from email.mime.text import MIMEText
    
    # Send HTML ONLY (no plain text alternative)
    # This forces Gmail to render HTML
    message = MIMEText(html_content, 'html', 'utf-8')
    message['To'] = to
    message['From'] = sender
    message['Subject'] = subject
    message['MIME-Version'] = '1.0'
    
    # Encode for Gmail API
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw_message}

def clean_html_for_email(html_content):
    """
    Optimize HTML content for email clients while preserving structure.
    Keep DOCTYPE, html, head, body tags for proper rendering.
    """
    import re
    
    # KEEP the HTML structure - DO NOT remove DOCTYPE, html, head, body tags!
    # Email clients NEED these tags to render HTML properly
    
    # Only remove external style blocks (inline styles are fine)
    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
    
    # Ensure proper spacing and formatting
    html_content = html_content.strip()
    
    return html_content

def send_smtp_email(to_email, from_email, subject, html_content):
    """Send email using SMTP with HTML-only content (force HTML rendering)"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        
        logger.info(f"Email Marketing: Sending SMTP email to {to_email}")
        
        # Send HTML ONLY (no plain text alternative)
        # This forces email clients to render HTML
        msg = MIMEText(html_content, 'html', 'utf-8')
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg['MIME-Version'] = '1.0'
        
        # Get SMTP credentials from environment
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_username = os.getenv('SMTP_USERNAME', from_email)
        smtp_password = os.getenv('SMTP_PASSWORD', '')
        
        if not smtp_password:
            # Try to use the same email as username and check for app password
            smtp_password = os.getenv('GMAIL_APP_PASSWORD', '')
            
        if not smtp_password:
            logger.warning("No SMTP password found. Please set GMAIL_APP_PASSWORD in .env")
            return False
        
        # Send email via SMTP
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Enable TLS encryption
        server.login(smtp_username, smtp_password)
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        
        logger.info(f"Email Marketing: SMTP email sent successfully to {to_email}")
        return True
        
    except Exception as smtp_error:
        logger.error(f"Email Marketing: SMTP sending failed: {smtp_error}")
        return False

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