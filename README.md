# Google Sheets MCP Server 🔗📊

## LATEST VERSION. 2
## This version works with skincare, wardrobe, food business sheets. 
## Right now it just takes one item order at a time
## Order update or delete is not implemented yet.

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.12.5+-green.svg)](https://pypi.org/project/fastmcp/)
[![Google Sheets API](https://img.shields.io/badge/Google%20Sheets-API%20v4-red.svg)](https://developers.google.com/sheets/api)

**Advanced MCP server that connects OpenAI Agents to Google Sheets for automated business operations with intelligent column detection and streamlined order processing.**

## 🏗️ System Architecture

### **Core Components**

| Component | Purpose | Lines of Code | Key Features |
|-----------|---------|---------------|--------------|
| **`server.py`** | MCP Server Core | 780 | 2 tools, OAuth, smart column detection |
| **`client.py`** | OpenAI Agent | 112 | Customer service interface |
| **`connection.json`** | Configuration | - | Sheet IDs, OAuth tokens |
| **`google_client_secret.json`** | OAuth Credentials | - | Google API authentication |

### **Data Flow Architecture**
```
Customer Query → Agent (client.py) → MCP Server (server.py) → Google Sheets API → Response
```

## 🛠️ MCP Tools Overview

The server implements **2 specialized tools** for comprehensive business operations:

### **1. `google_sheets_query_tool(query: str)`**
- **Purpose**: Main customer-facing tool for product inquiries
- **Usage**: Product searches, availability checks, pricing questions
- **Example**: `"wall clock"` → Returns matching products with details
- **Features**: Intelligent product matching, stock status reporting

### **2. `process_customer_order_tool(customer_name, product_name, quantity, ...)`**
- **Purpose**: Complete end-to-end order processing (PRIMARY TOOL)
- **Features**: 
  - ✅ Automatic product validation
  - ✅ Inventory updates (stock reduction)
  - ✅ Order recording with all details
  - ✅ Returns formatted order summary
  - ✅ Duplicate order prevention (30-second window)
- **Parameters**: `customer_name`, `product_name`, `quantity`, `customer_email`, `notes`, `customer_address`, `payment_mode`

## 🧠 Advanced Features

### **Smart Column Detection System**
The server includes an intelligent column mapping system that automatically detects and maps spreadsheet columns:

```python
# Automatic column type detection
"product_name": ["item_name", "product_name", "product_title", "name", "product"]
"quantity": ["quantity", "qty", "stock", "available", "inventory"]
"price": ["unit_price", "price", "cost", "amount", "rate", "pkr"]
"id": ["item_id", "product_id", "id", "sku", "code"]
```

**Benefits:**
- Works with any spreadsheet column naming convention
- Prioritizes exact matches over partial matches
- Supports multiple business types (retail, service, manufacturing)

### **Order Processing Architecture**
**Streamlined Single-Tool Flow:**
1. Customer inquiry → `google_sheets_query_tool()`
2. Order placement → `process_customer_order_tool()` (handles everything)
3. Automatic inventory update and order recording
4. Formatted order summary returned to customer

### **OAuth 2.0 Integration**
- **Secure Authentication**: Google OAuth 2.0 with refresh tokens
- **Token Management**: Automatic token refresh and preservation
- **Scope**: Google Sheets API v4 access

### **Logging & Debugging**
- **Comprehensive Logging**: JSON RPC message logging enabled
- **Debug Information**: Column mapping, product search, order processing
- **Error Handling**: Detailed error reporting with context

## 🚀 Quick Setup

### **1. Install Dependencies**
```bash
pip install -e .
```

### **2. Google OAuth Setup**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project → Enable Google Sheets API & Drive API  
3. Create OAuth 2.0 credentials → Download as `google_client_secret.json`

### **3. Configure Your Sheets**
```bash
python setup.py
```
Follow the prompts to:
- Authorize Google access
- Select your spreadsheet
- Choose inventory and orders sheets

### **4. Run Your System**
```bash
# Terminal 1 - Start MCP Server (Port 8010)
python server.py

# Terminal 2 - Start OpenAI Agent
python client.py
```

## 📋 Spreadsheet Requirements

### **Inventory Sheet Columns** (Auto-detected)
- Product ID/SKU
- Product Name
- Category (optional)
- Stock Quantity
- Unit Price
- Stock Status

### **Orders Sheet Columns** (Auto-detected)
- Order ID
- Product
- Quantity  
- Unit Price
- Total Price
- Payment Type
- Order Status
- Customer Name
- Customer Email
- Delivery Address

## 🔧 Configuration Files

### **`connection.json`** Structure
```json
{
  "inventory": {
    "workbook_id": "your-sheet-id",
    "worksheet_name": "inventory-sheet-name"
  },
  "orders": {
    "workbook_id": "your-sheet-id", 
    "worksheet_name": "orders-sheet-name"
  },
  "refresh_token": "your-oauth-refresh-token",
  "spreadsheet_name": "Your Business Name"
}
```

## 🤖 Agent Capabilities

Your OpenAI Agent can now:
- ✅ **Answer product questions** intelligently
- ✅ **Check real-time inventory** and availability
- ✅ **Process customer orders** end-to-end
- ✅ **Update stock automatically** after orders
- ✅ **Record detailed orders** in Google Sheets
- ✅ **Handle payment modes** (COD/Online)
- ✅ **Prevent duplicate orders** automatically
- ✅ **Generate order summaries** for customers

## 🛡️ Error Handling & Features

- **Duplicate Prevention**: 30-second order deduplication window
- **Stock Validation**: Automatic availability checking
- **Missing Information**: Intelligent prompts for required customer data
- **Flexible Schema**: Works with any spreadsheet column structure
- **Robust Authentication**: Automatic OAuth token refresh

## 🔍 Technical Implementation

### **Key Technical Features:**
1. **FastMCP Framework**: Modern MCP server implementation
2. **Smart Column Detection**: Automatic spreadsheet schema analysis
3. **OAuth 2.0 Integration**: Secure Google API authentication
4. **Duplicate Prevention**: Order deduplication with time-based caching
5. **Comprehensive Logging**: JSON RPC and debug message logging
6. **Error Recovery**: Graceful handling of API errors and timeouts

### **Dependencies:**
- `fastmcp>=2.12.5` - MCP server framework
- `google-api-python-client>=2.185.0` - Google Sheets API
- `google-auth>=2.41.1` - OAuth authentication
- `openai-agents>=0.4.0` - OpenAI Agents SDK
- `uvicorn[standard]>=0.38.0` - ASGI server

## 📊 Current Status

**✅ FULLY OPERATIONAL** - The agent successfully:
- Processes orders and updates inventory automatically
- Works with multiple spreadsheet formats (decor inventory, wardrobe inventory, etc.)
- Provides real-time customer service through Google Sheets integration
- Maintains order history and customer data

---

**Built with ❤️ for automated business operations**

That's it! No complex dashboard or config management needed.