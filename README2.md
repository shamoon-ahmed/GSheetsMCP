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

---

# 🎨 Marketing Tools for AI-Powered Poster Generation

In addition to order management, this MCP server includes **3 powerful marketing tools** designed for automated poster generation using Google Gemini AI. These tools work together to create professional marketing materials directly from your product inventory data.

## 🛠️ **Marketing Tools (3 Additional Tools)**

The marketing agent will use total 4 tools. `google_sheets_query_tool` which is already made. And new tools below

### **🔍 Product Search Tool**

8. **`search_product_tool`**
   - **Purpose:** Search and retrieve complete product details from inventory for marketing use
   - **Input:** Product name (partial matches supported)
   - **Output:** Complete product information including price, weight, quantity, media URLs, and marketing tags
   - **Schema Support:** ItemID | Product Name | Price (PKR) | Weight | Quantity | Status | Media | Tags
   - **Example Usage:** 
     ```json
     search_product_tool("Aloe Vera Gel")
     → Returns: {product_name, price, weight, quantity, status, media_url, tags}
     ```

### **📝 Prompt Engineering Tool**

9. **`prompt_structure_tool`**
   - **Purpose:** Create optimized marketing prompts for AI poster generation
   - **Input:** Product details JSON + poster style preference
   - **Output:** Professional marketing prompt optimized for Gemini AI
   - **Available Styles:**
     - `professional` - Clean, corporate design with navy/white/gold colors
     - `vibrant` - Bold, energetic with bright colors and dynamic shapes
     - `minimal` - Sophisticated, clean lines with premium typography
     - `luxury` - Elegant gold/black color schemes for premium products
     - `modern` - Contemporary, trendy designs for Instagram-ready aesthetics
   - **Example Usage:**
     ```json
     prompt_structure_tool(product_details, "professional")
     → Returns: Structured marketing prompt with design requirements
     ```

### **🖼️ AI Image Generation Tool**

10. **`generate_images_tool`**
    - **Purpose:** Generate marketing posters using Google Gemini 2.5 Flash Image API
    - **Input:** Marketing prompt + optional product image URL
    - **Output:** Base64 encoded poster images or file paths
    - **Features:**
      - Works with prompt-only or prompt + existing product images
      - Supports product images from Google Sheets Media column
      - Multiple output formats (base64, file)
      - Real-time API integration with Gemini AI
    - **Requirements:** Paid Gemini API tier for image generation
    - **Example Usage:**
      ```json
      generate_images_tool(marketing_prompt, product_image_url, "base64")
      → Returns: Generated poster as base64 image data
      ```

## 🎯 **Marketing Workflow**

### **Complete Marketing Automation Process:**

1. **🔍 Product Search** → `search_product_tool("Coconut Lip Balm")`
   - Retrieves product details from inventory
   - Includes price, features, media URLs, marketing tags

2. **📝 Prompt Creation** → `prompt_structure_tool(product_data, "professional")`
   - Converts product data into optimized marketing prompt
   - Applies style-specific design requirements

3. **🖼️ Image Generation** → `generate_images_tool(prompt, media_url)`
   - Generates professional poster using Gemini AI
   - Combines product data with AI-powered design

### **End-to-End Example:**
```
Input: "Create a professional poster for Coconut Lip Balm"

1. Search: search_product_tool("Coconut Lip Balm")
   → {name: "Coconut Lip Balm", price: "400 PKR", tags: "moisturizing, coconut, daily-use"}

2. Prompt: prompt_structure_tool(product_data, "professional") 
   → "Create a clean, professional marketing poster for 'Coconut Lip Balm' priced at 400..."

3. Generate: generate_images_tool(marketing_prompt, product_image_url)
   → Base64 encoded professional poster image
```

## ⚙️ **Marketing Setup Requirements**

### **Environment Configuration:**
```env
# Required for marketing tools
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL_NAME=gemini-2.5-flash-image-preview

# Existing Google Sheets config
INVENTORY_SHEET_ID=your_sheet_id
INVENTORY_WORKSHEET_NAME=your_sheet_name
GOOGLE_REFRESH_TOKEN=your_refresh_token
```

### **Google Sheets Schema for Marketing:**
Your inventory sheet should include these additional columns for marketing:

| Column | Purpose | Example |
|--------|---------|---------|
| **Media** | Product image URLs | `https://example.com/product.jpg` |
| **Tags** | Marketing keywords | `moisturizing, organic, daily-use` |

**Complete Marketing-Ready Inventory Example:**
```
| Product Name    | Price | Weight | Quantity | Status   | Media                    | Tags                     |
|-----------------|-------|--------|----------|----------|--------------------------|--------------------------|
| Aloe Vera Gel   | 950   | 100ml  | 15       | In Stock | https://amazon.com/...   | soothing, hydration, cooling |
| Coconut Lip Balm| 400   | 20g    | 30       | In Stock | https://images.com/...   | lip-care, moisturizing, coconut |
```

## 🚀 **Marketing Use Cases**

### **Automated Social Media Content**
- Generate Instagram-ready product posters
- Create Facebook marketplace images
- Produce promotional material for stories

### **E-commerce Product Images** 
- Professional product photography alternatives
- Consistent branding across product listings
- Quick poster generation for new products

### **Print Marketing Materials**
- Flyers and brochures for physical stores
- Product catalog images
- Promotional banners and signage

### **Bulk Marketing Automation**
- Generate posters for entire product inventory
- Create seasonal promotional materials
- Batch process products with different styles

## 💡 **Marketing Benefits**

- **🤖 AI-Powered Design** - Professional posters without graphic design skills
- **⚡ Instant Generation** - Create marketing materials in seconds
- **🎨 Multiple Styles** - Choose from 5 different design aesthetics
- **📊 Data-Driven** - Uses real inventory data for accurate pricing and details
- **🔗 Seamless Integration** - Works with existing inventory management system
- **💰 Cost-Effective** - No need for expensive design software or freelancers

---

*The marketing tools extend the order management capabilities with AI-powered visual content creation, providing a complete business automation solution from inventory management to marketing material generation.*

---

# 📧 Email Marketing Automation Tools

This README is AI generated but what exactly happening is:
- when sending email for approval to business owner's email, it doesn't send complete email design.
- and when sending it to all customer's email, it sends raw html or bad format. not the real designed email
 
-------------------------
Building on the poster generation capabilities, this MCP server includes **4 advanced email marketing tools** that create, approve, and send AI-powered email campaigns to your customers. These tools provide complete email marketing automation with professional design and approval workflows.

## 🛠️ **Email Marketing Tools (4 Additional Tools)**

### **✍️ AI Email Content Generation**

11. **`generate_email_content_tool`**
    - **Purpose:** Generate professional HTML email templates using OpenAI GPT-4o
    - **Input:** Product details + email style + business branding
    - **Output:** Complete responsive HTML email with subject line
    - **Email Styles:**
      - `promotional` - Sales-focused with clear CTAs and pricing emphasis
      - `newsletter` - Informative content with product highlights
      - `sale` - Discount-focused with urgency and savings messaging
      - `announcement` - New product launches and company updates
    - **Features:**
      - Mobile-responsive table-based HTML layout
      - Inline CSS for maximum email client compatibility
      - Automatic subject line generation
      - Template fallback when AI is unavailable
    - **Example Usage:**
      ```json
      generate_email_content_tool(product_details, "promotional", "", "", "MY SKINCARE!")
      → Returns: Complete HTML email + subject line ready for approval
      ```

### **👔 Email Design Approval System**

12. **`get_email_design_approval_tool`**
    - **Purpose:** Send email previews to business owner for campaign approval
    - **Input:** HTML email content + subject line + owner email
    - **Output:** Professional approval email with visual preview and instructions
    - **Features:**
      - **Smart Content Extraction** - Automatically detects product names, prices, features
      - **Visual Email Preview** - Shows both summary cards and actual HTML rendering
      - **Approval Instructions** - Clear respond-with options (APPROVED/REVISE/CANCEL)
      - **Mobile-Friendly Preview** - Responsive design preview display
      - **Currency Support** - Properly handles ₹, $, € symbols in content
    - **Approval Options:**
      - Reply "APPROVED" → Campaign ready to send
      - Reply "CANCEL" → Campaign cancelled
      - Reply with changes → "make text bigger, change color to blue"
    - **Example Usage:**
      ```json
      get_email_design_approval_tool(email_html, subject, "owner@business.com", "Please review this Aloe Vera campaign")
      → Sends approval email with preview and instructions
      ```

### **📬 Mass Email Campaign Delivery**

13. **`send_emails_tool`**
    - **Purpose:** Send approved email campaigns to all customers from orders database
    - **Input:** Approved email content + campaign details
    - **Output:** Campaign delivery report with success/failure metrics
    - **Features:**
      - **Customer Email Extraction** - Automatically finds customer emails from orders sheet
      - **Dual Delivery Methods** - Gmail API primary, SMTP fallback
      - **Campaign Tracking** - Unique campaign IDs and delivery statistics
      - **Test Mode** - Send to sender only for testing before mass delivery
      - **Rate Limiting** - Prevents email service throttling
      - **Error Handling** - Graceful failure recovery with fallback delivery
    - **Delivery Methods:**
      - Gmail API (primary) - High deliverability, bulk sending
      - SMTP Fallback - Gmail app password authentication
    - **Example Usage:**
      ```json
      send_emails_tool(approved_html, "Special Offer: Aloe Vera Gel ₹950!", "business@email.com", "Aloe Vera Campaign", false)
      → Sends to all customers, returns delivery report
      ```

## 🎯 **Complete Email Marketing Workflow**

### **End-to-End Campaign Process:**

1. **📧 Content Generation** → `generate_email_content_tool()`
   - AI creates professional HTML email with your product
   - Includes mobile-responsive design and clear call-to-actions
   - Generates compelling subject line automatically

2. **👀 Design Approval** → `get_email_design_approval_tool()`
   - Sends preview to business owner via email
   - Shows visual email preview with extracted promotional info
   - Provides simple approval/revision workflow

3. **🚀 Campaign Delivery** → `send_emails_tool()`
   - Sends approved email to all customers
   - Tracks delivery success and generates reports
   - Handles errors and provides fallback delivery

### **Real Campaign Example:**
```
Scenario: Launch campaign for Aloe Vera Gel (₹950)

1. Generate Content:
   generate_email_content_tool(aloe_product_data, "promotional", "", "", "MY SKINCARE!")
   → Creates professional email with product image, benefits, pricing, CTA

2. Get Approval:
   get_email_design_approval_tool(email_html, "Special Offer: Aloe Vera Gel ₹950!", "owner@email.com")
   → Owner receives preview email with:
     - Product: "Aloe Vera Gel"  
     - Price: "₹950"
     - Features: ["Soothing", "Hydration", "Cooling"]
     - Visual HTML preview

3. Send Campaign (after "APPROVED" reply):
   send_emails_tool(approved_html, subject, "business@email.com", "Aloe Vera Launch")
   → Delivers to all customers: "✅ Successfully sent to 47 customers!"
```

## ⚙️ **Email Marketing Setup Requirements**

### **Environment Configuration:**
```env
# OpenAI for email content generation
OPENAI_API_KEY=your_openai_api_key_here

# Gmail configuration for sending
GOOGLE_REFRESH_TOKEN=your_refresh_token
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
GMAIL_APP_PASSWORD=your_gmail_app_password

# Existing inventory/orders config
ORDERS_SHEET_ID=your_orders_sheet_id
ORDERS_WORKSHEET_NAME=your_orders_worksheet_name
```

### **Customer Email Requirements:**
Your **orders sheet** must include customer email addresses in any of these column formats:
- `customer_email`, `email`, `customer email`, `Email`, `Customer Email`

**Example Orders Sheet with Email Marketing Support:**
```
| Order No | Item Name     | Customer Name | Customer Email        | Address      | Status |
|----------|---------------|---------------|-----------------------|--------------|--------|
| ORD-001  | Aloe Vera Gel | John Doe      | john@email.com        | City ABC     | Delivered |
| ORD-002  | Face Cream    | Jane Smith    | jane.smith@email.com  | Town XYZ     | Pending |
```

## 📊 **Email Marketing Features**

### **🎨 Professional Email Design**
- **Mobile-Responsive Layout** - Works on all devices and email clients
- **Table-Based Structure** - Maximum compatibility with Gmail, Outlook, Apple Mail
- **Inline CSS Styling** - No external dependencies, renders everywhere
- **Email-Optimized Images** - Proper scaling and fallbacks

### **🤖 AI-Powered Content Creation**
- **OpenAI GPT-4o Integration** - Latest AI model for email copywriting
- **Product-Aware Generation** - Extracts product details intelligently
- **Style Customization** - Multiple email template styles available
- **Subject Line Optimization** - AI-generated engaging subject lines

### **✅ Professional Approval Process**
- **Visual Email Preview** - See exactly how customers will receive it
- **Smart Content Detection** - Automatically extracts prices, products, features
- **Simple Approval Workflow** - Reply-based approval system
- **Revision Support** - Request specific changes via email reply

### **📈 Campaign Management**
- **Automated Customer Targeting** - Uses existing orders database
- **Delivery Tracking** - Success/failure reporting per campaign
- **Test Mode** - Send to yourself first before mass delivery
- **Dual Delivery Systems** - Gmail API + SMTP fallback reliability

## 🚀 **Email Marketing Use Cases**

### **Product Launch Campaigns**
- Generate emails for new inventory items
- Include product images, pricing, and benefits
- Send to all existing customers automatically

### **Promotional Sales**
- Create discount and sale announcement emails
- Highlight special offers with compelling CTAs
- Track campaign performance and delivery

### **Seasonal Marketing**
- Holiday promotions and themed campaigns
- Seasonal product recommendations
- Customer re-engagement campaigns

### **Inventory Management Integration**
- Email campaigns for overstocked items
- New arrival notifications
- Back-in-stock alerts for popular products

## 💡 **Email Marketing Benefits**

- **🎯 Targeted Campaigns** - Uses real customer data from orders
- **⚡ Rapid Deployment** - Generate, approve, and send in minutes
- **📱 Mobile-First Design** - Professional rendering on all devices
- **🤖 AI Content Creation** - No copywriting skills required
- **✅ Quality Control** - Built-in approval process prevents mistakes
- **📊 Performance Tracking** - Delivery reports and campaign metrics
- **💰 Cost-Effective** - Complete email marketing solution in one tool

### **Complete Business Automation Stack**
```
📊 Order Management → 🎨 Poster Generation → 📧 Email Marketing
     ↓                        ↓                      ↓
  Track customers         Create visuals         Engage customers
  Manage inventory       Generate content       Drive sales
  Process orders         AI-powered design      Automated delivery
```

---

*The email marketing tools complete the business automation suite, providing end-to-end customer engagement from order processing to visual content creation to automated email campaigns. This creates a comprehensive solution for modern e-commerce and retail businesses.*