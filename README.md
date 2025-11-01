# Google Sheets MCP Server 🔗

# LATEST 1 --- 
## RIGHT NOW THE AGENT APPENDS THE ORDER IN ORDERS SHEET AND INVENTORY IS ALSO UPDATED - RIGHT NOW WORKING WITH:
## SKINCARE INVENTORY AND WARDROBE INVENTORY

Simple MCP server that connects OpenAI Agents to Google Sheets for automated business operations.

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install -e .
```

### 2. Get Google OAuth Credentials
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project → Enable Google Sheets API & Drive API
3. Create OAuth 2.0 credentials → Download as `google_client_secret.json`

### 3. Setup Your Sheets
```bash
python simple_setup.py
```
Follow the prompts to:
- Authorize Google access
- Select your spreadsheet  
- Choose inventory and orders sheets

### 4. Run Your System
```bash
# Terminal 1 - Start MCP Server
python server.py

# Terminal 2 - Start Your Agent  
python client.py
```

## � Your Agent Can Now:
- ✅ Answer product questions
- ✅ Check inventory/availability  
- ✅ Process customer orders
- ✅ Update stock automatically
- ✅ Record orders in Google Sheets

## 🔧 Files You Need:
- `server.py` - MCP server (already working)
- `client.py` - Your OpenAI agent (already working)  
- `simple_setup.py` - One-time configuration
- `connection.json` - Created by setup (contains your sheet config)

That's it! No complex dashboard or config management needed.