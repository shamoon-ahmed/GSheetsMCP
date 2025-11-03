"""
Simple Google Sheets MCP Setup
"""

import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

def setup():
    print("🔗 Google Sheets MCP Setup")
    print("=" * 30)
    
    # Check credentials
    if not os.path.exists("google_client_secret.json"):
        print("❌ google_client_secret.json not found!")
        return
    
    print("1. Opening browser for Google authorization...")
    
    # OAuth flow with console fallback for better compatibility
    flow = InstalledAppFlow.from_client_secrets_file(
        "google_client_secret.json",
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
    )
    
    # Configure flow for offline access to get refresh token
    flow.redirect_uri = 'http://localhost:8080/'
    
    # Try local server first, fallback to console if fails
    try:
        credentials = flow.run_local_server(port=8080, open_browser=True, access_type='offline', prompt='consent')
    except Exception as e:
        print(f"⚠️ Local server failed: {e}")
        print("🔧 Falling back to console authorization...")
        credentials = flow.run_console()
    print("✅ Authorization successful!")
    
    # Connect to Google APIs
    print("2. Connecting to Google Sheets...")
    drive = build('drive', 'v3', credentials=credentials)
    sheets = build('sheets', 'v4', credentials=credentials)
    
    # Get spreadsheets
    print("3. Finding your spreadsheets...")
    result = drive.files().list(
        q="mimeType='application/vnd.google-apps.spreadsheet'",
        orderBy='modifiedTime desc',
        pageSize=10
    ).execute()
    
    spreadsheet_list = result.get('files', [])
    if not spreadsheet_list:
        print("❌ No spreadsheets found")
        return
    
    print(f"📊 Found {len(spreadsheet_list)} spreadsheets:")
    for i, sheet in enumerate(spreadsheet_list, 1):
        print(f"   {i}. {sheet['name']}")
    
    # Select spreadsheet
    choice = int(input(f"4. Choose spreadsheet (1-{len(spreadsheet_list)}): "))
    selected = spreadsheet_list[choice - 1]
    sheet_id = selected['id']
    print(f"✅ Selected: {selected['name']}")
    
    # Get worksheets
    print("5. Getting worksheets...")
    metadata = sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
    worksheets = metadata.get('sheets', [])
    
    print("📋 Available worksheets:")
    for i, ws in enumerate(worksheets, 1):
        name = ws['properties']['title']
        print(f"   {i}. {name}")
    
    # Select inventory sheet
    inv_choice = int(input(f"6. Choose INVENTORY worksheet (1-{len(worksheets)}): "))
    inventory_name = worksheets[inv_choice - 1]['properties']['title']
    
    # Select orders sheet
    ord_choice = int(input(f"7. Choose ORDERS worksheet (1-{len(worksheets)}): "))
    orders_name = worksheets[ord_choice - 1]['properties']['title']
    
    # Always use the new refresh token from the OAuth flow
    refresh_token = credentials.refresh_token
    if refresh_token:
        print("💡 Successfully captured new refresh token")
    else:
        print("⚠️ Warning: No refresh token received from OAuth flow")
    
    # Save connection.json
    config = {
        "inventory": {
            "workbook_id": sheet_id,
            "worksheet_name": inventory_name
        },
        "orders": {
            "workbook_id": sheet_id,
            "worksheet_name": orders_name
        },
        "refresh_token": refresh_token,
        "spreadsheet_name": selected['name']
    }
    
    with open("connection.json", "w") as f:
        json.dump(config, f, indent=2)
    
    print("\n✅ Setup complete!")
    print(f"📊 Spreadsheet: {selected['name']}")
    print(f"📦 Inventory: {inventory_name}")
    print(f"📋 Orders: {orders_name}")
    print("💾 Saved to connection.json")
    print("\n🚀 Ready to run:")
    print("   python server.py")
    print("   python client.py")

if __name__ == "__main__":
    setup()