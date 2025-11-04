# 📊 Google Sheets MCP Server

As we're focusing on a functional prototype, to showcase a demo of our application, the tools for this Google Sheets MCP Server works for businesses.

## 🎯 **Supported Business Types**

This MCP server is designed to work seamlessly with various business models:

- **🧴 Skincare & Beauty** - Product inventory with weights, brands, prices
- **👕 Wardrobe & Fashion** - Clothing items with sizes, colors, variants  
- **🍕 Food & Restaurant** - Menu items, combos, pricing, ingredients
- **🛍️ General Retail** - Any product-based business with inventory

## 🗂️ **Required Google Sheets Structure**

For the system to work accurately, your Google Sheets should follow this structure:

### **📋 Inventory Sheet (EXAMPLE)**
Your inventory sheet should contain these column types (exact names can vary):

| Column Type | Example Names | Purpose |
|-------------|---------------|---------|
| **Product Name** | `Product Name`, `Item Name`, `Title` | Main product identifier |
| **Price** | `Price (PKR)`, `Cost`, `Amount`, `Rate` | Product pricing |
| **Quantity** | `Quantity`, `Stock`, `Available`, `Inventory` | Stock levels |
| **Weight** | `Weight`, `Volume`, `ML`, `Grams` | Product weight/volume |
| **Color** | `Color`, `Colour`, `Shade` | Product color variants |
| **Size** | `Size`, `Dimensions`, `Variant` | Product size options |
| **Status** | `Status`, `Availability`, `Active` | Product availability |

**Example Inventory Structure:**
```
| Product Name           | Price (PKR) | Weight | Color | Size | Quantity | Status    |
|------------------------|-------------|--------|-------|------|----------|-----------|
| Face Wash              | 850         | 100ml  | Clear | Med  | 20       | In Stock  |
| Red Shirt Large        | 2000        | 200g   | Red   | L    | 15       | In Stock  |
| Margherita Pizza       | 1200        | 300g   | -     | Med  | -        | Available |
```

### **📝 Orders Sheet (EXAMPLE)**
Your orders sheet should contain these column types:

| Column Type | Example Names | Purpose |
|-------------|---------------|---------|
| **Order ID** | `Order No`, `Order ID`, `OrderID` | Unique order identifier |
| **Product Name** | `Item Name`, `Product`, `Items` | Ordered products |
| **Quantity** | `Quantity`, `Qty`, `Amount` | Order quantities |
| **Weight** | `Weight`, `Total Weight` | Product weights |
| **Customer Name** | `Customer Name`, `Customer` | Customer information |
| **Customer Email** | `Customer Email`, `Email` | Contact information |
| **Address** | `Delivery Address`, `Address` | Delivery location |
| **Payment** | `Payment Mode`, `Payment Method` | Payment type |
| **Total** | `Subtotal (PKR)`, `Total`, `Amount` | Order total |
| **Status** | `Status`, `Order Status` | Order state |

## 🛠️ **Available Tools (7 Total)**

### **🔍 Query & Information Tools**

1. **`google_sheets_query_tool`**
   - **Purpose:** Search inventory, check product availability, get pricing information
   - **Usage:** Answers customer questions about products, stock levels, and prices
   - **Example:** "Do you have face wash in stock? What's the price?"

### **📦 Single Product Order Tools**

2. **`process_customer_order_tool`**
   - **Purpose:** Create new orders for single products
   - **Usage:** When customers order one type of item
   - **Example:** "I want 3 pizzas" → Creates single product order

3. **`update_customer_order_tool`**
   - **Purpose:** Modify existing single product orders
   - **Usage:** Change quantity, product, or customer details in existing order
   - **Example:** Update order ORD-123 to change quantity from 2 to 5

4. **`cancel_customer_order_tool`**
   - **Purpose:** Cancel single product orders
   - **Usage:** Remove order and restore inventory
   - **Example:** Cancel order ORD-123 and add products back to stock

### **🛒 Multiple Products Order Tools**

5. **`process_multiple_products_order_tool`**
   - **Purpose:** Create orders with multiple different products
   - **Usage:** When customers order combinations of items
   - **Example:** "I want 2 pizzas, 3 cokes, and 1 fries" → Creates multi-product order

6. **`update_multiple_products_order_tool`**
   - **Purpose:** Modify existing multiple products orders
   - **Usage:** Change products, quantities, or customer information
   - **Example:** Update order to remove pizza and add burger instead

7. **`cancel_multiple_products_order_tool`**
   - **Purpose:** Cancel multiple products orders
   - **Usage:** Remove entire order and restore all inventory
   - **Example:** Cancel order ORD-456 with multiple items

## ⚡ **Key Features**

- **🤖 Smart Column Detection** - Automatically detects your spreadsheet structure
- **📊 Real-time Inventory Sync** - Updates stock levels after each order
- **🔄 Dynamic Business Support** - Works with inventory-based and service businesses
- **💰 Automatic Pricing** - Calculates totals and handles multiple currencies
- **🔍 Intelligent Product Matching** - Finds products even with variant names
- **📱 OAuth Integration** - Secure Google Sheets authentication
- **⚠️ Error Handling** - Graceful handling of stock shortages and invalid data

## 🚀 **How It Works**

1. **Customer Inquiry** → System queries inventory for availability
2. **Order Processing** → Creates order with automatic ID generation  
3. **Inventory Update** → Reduces stock levels in real-time
4. **Order Tracking** → Saves complete order details with customer info
5. **Modification Support** → Allows updates and cancellations with inventory restoration

## 📋 **Use Cases**

### **Skincare Business**
- Track product inventory with weights and brands
- Process orders for face wash, moisturizers, serums
- Handle product combinations and bundles

### **Fashion/Wardrobe Business**  
- Manage clothing inventory with sizes and colors
- Process orders for shirts, pants, accessories
- Track variants and availability

### **Food/Restaurant Business**
- Manage menu items and combinations
- Process food orders with multiple items
- Handle both inventory tracking and unlimited service items

## 🔧 **Setup Requirements**

1. **Google Sheets** with proper inventory and orders structure
2. **OAuth Credentials** for Google Sheets API access
3. **Connection Configuration** linking to your specific spreadsheets
4. **MCP Client** to interact with the server tools

---

To start testing, go with this flow defined below. We'll use this for demo as well

For example a wardrobe business:
- Inventory Sheet: <br>
Item ID	| Item Name	| Size | Color	| Quantity	| Unit Price (PKR)	| Status

- Orders Sheet: <br>
Order No | Item Name | Size	Color | Quantity | Subtotal(PKR) | Payment Mode | Customer Name | Customer Email | Delivery Address | Status

<br>

OR a food business:
- Food Menu Sheet: <br>
ItemID | Menu Item Name | Category | Description / Key Ingredients | Food Cost (PKR) | Availability (Daily/Limited)

- Orders Sheet: <br>
OrderID | Item  | Customer Name | Subtotal | Payment | Quantity | Email | Delivery Address | Status

<br>

OR a skincare business:
- Skincare products Sheet: <br>
ItemID | Product Name | Price (PKR) | Weight | Quantity | Status

- Skincare orders Sheet: <br>
Order No | Item Name | Weight | Quantity | Subtotal (PKR) | Payment Mode | Customer Name | Customer Email | Delivery Address | Status

---

*This MCP server provides a complete order management solution that adapts to your business needs while maintaining accurate inventory control and customer order tracking.*