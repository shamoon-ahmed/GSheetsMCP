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

## 🛠️ **Available Tools (13 Total)**

**Order Management (7 tools)** → **Marketing Automation (3 tools)** → **Email Marketing (3 tools)**

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

<br>

The flow is:
- User says "Create a promotional poster for lavender lotion. It should be forest themed."
The agent will first use the `google_sheets_query_tool` to get all the products data in the inventory.
- Agent sees the correct name is "Lavender Body Lotion" and passes it into `search_product_tool` to get all the details of that specific product.
- Then it uses `prompt_structure_tool` and passes the product details it got from the output of `search_product_tool` and it passes the main query from the user as the user prompt.
- Now that the agent has the prompt to generate images, it passes that prompt into `generate_images_tool` and generates the promotional poster for Lavender Body Lotion and also a social media caption.

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
   - **Example Usage:**
     ```json
     prompt_structure_tool(product_details, user_prompt)
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
      → Returns: Generated poster as base64 image data and a social media caption
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
   - Generates a social media caption as well

### **End-to-End Example:**
```
Input: "Create a professional poster for Coconut Lip Balm"

1. Search: search_product_tool("Coconut Lip Balm")
   → {name: "Coconut Lip Balm", price: "400 PKR", tags: "moisturizing, coconut, daily-use"}

2. Prompt: prompt_structure_tool(product_data, "professional") 
   → "Create a clean, professional marketing poster for 'Coconut Lip Balm' priced at 400..."

3. Generate: generate_images_tool(marketing_prompt, product_image_url)
   → Base64 encoded professional poster image with caption
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

Building on the poster generation capabilities, this MCP server includes **3 email marketing tools** that create, approve, and send professional HTML email campaigns to your customers. These tools provide complete email marketing automation with a beautiful dark-themed design and approval workflows.

## 🛠️ **Email Marketing Tools (3 Additional Tools)**

The Agent will also use the `google_sheets_query_tool` to get the correct product name, price and image url so that correct arguments are passed in `email_content_tool`

<br>

So basically, email marketing has 4 tools in total.

### **✍️ Email Content Generation**

11. **`email_content_tool`**
    - **Purpose:** Generate professional dark-themed HTML email templates for product campaigns
    - **Input:** Product name + price + image URL + shop link + company name
    - **Output:** Complete responsive HTML email with subject line
    - **Design Features:**
      - Dark theme (#1a1a1a background) with pink accents (#ff99aa)
      - Mobile-responsive table-based layout (600px width)
      - Professional product image display with rounded corners
      - Clear call-to-action "Shop Now" button
      - Inline CSS for maximum email client compatibility
      - Automatic subject line generation with emoji
    - **Example Usage:**
      ```json
      email_content_tool("Lavender Body Lotion", "1600", "https://image-url.com/product.jpg", "https://shop.com", "SahulatAI SkinCare")
      → Returns: {
           "success": true,
           "email_content": "<html>...",
           "email_subject": "✨ Introducing Lavender Body Lotion - Just for 1600!",
           "product_featured": "Lavender Body Lotion",
           "ready_for_approval": true
         }
      ```

### **👔 Email Design Approval System**

12. **`get_email_design_approval_tool`**
    - **Purpose:** Send email preview to business owner for campaign approval before mass sending
    - **Input:** HTML email content + subject line + owner email + optional approval message
    - **Output:** Approval email sent with campaign preview and instructions
    - **Features:**
      - **Full Campaign Preview** - Shows actual email design that customers will receive
      - **Approval Instructions Banner** - Blue header with clear approval/cancel options
      - **Visual Markers** - Green banners above/below campaign preview
      - **Simple Response System** - Reply "APPROVED" or "CANCEL" to the email
      - **Dual Delivery** - Gmail API primary, SMTP fallback for reliability
      - **Auto-Fix Technology** - Automatically handles HTML escaping issues
    - **Approval Options:**
      - Reply "APPROVED" → Proceed to mass sending with send_emails_tool
      - Reply "CANCEL" → Campaign cancelled, no emails sent
    - **Example Usage:**
      ```json
      get_email_design_approval_tool(email_html, "✨ Introducing Lavender Body Lotion - Just for 1600!", "owner@business.com", "Please review")
      → Sends approval email with full campaign preview
      ```

### **📬 Mass Email Campaign Delivery**

13. **`send_emails_tool`**
    - **Purpose:** Send approved email campaigns to all customers from orders database
    - **Input:** Approved email content + subject line + sender email + campaign name + test mode
    - **Output:** Campaign delivery report with success/failure statistics
    - **Features:**
      - **Automatic Customer Extraction** - Finds all customer emails from orders sheet
      - **Dual Delivery Methods** - Gmail API primary, SMTP fallback for each email
      - **Test Mode** - Send to sender email only for testing before full campaign
      - **Campaign Tracking** - Unique campaign IDs and delivery statistics
      - **Rate Limiting** - 0.1s delay between sends to prevent throttling
      - **Error Handling** - Graceful failure recovery with automatic SMTP fallback
      - **Auto-Fix Technology** - Handles HTML escaping issues automatically
    - **Delivery Methods:**
      - Gmail API (primary) - High deliverability, OAuth2 authentication
      - SMTP Fallback (automatic) - Gmail app password, TLS encryption
    - **Example Usage:**
      ```json
      send_emails_tool(approved_html, "✨ Introducing Lavender Body Lotion - Just for 1600!", "business@gmail.com", "Lavender Campaign", false)
      → Sends to all customers, returns: {
           "success": true,
           "emails_sent": 47,
           "failed_emails": 0,
           "campaign_id": "CAMP_1731334567",
           "message": "Successfully sent to 47 customers!"
         }
      ```

## 🎯 **Complete Email Marketing Workflow**

### **3-Step Campaign Process:**

1. **📧 Generate Email Content** → `email_content_tool()`
   - Creates professional dark-themed HTML email
   - Includes product image, pricing, features, and Shop Now button
   - Generates compelling subject line with emoji
   - Returns JSON with email_content and email_subject

2. **👀 Get Design Approval** → `get_email_design_approval_tool()`
   - Sends preview email to business owner
   - Shows full campaign design with approval instructions
   - Owner replies "APPROVED" or "CANCEL"
   - Validates campaign before mass sending

3. **🚀 Send Campaign** → `send_emails_tool()`
   - Sends approved email to all customers from orders sheet
   - Tracks delivery success and generates reports
   - Provides campaign ID and delivery statistics
   - Optional test mode to send to yourself first

### **Real Campaign Example:**
```
Scenario: Launch email campaign for Lavender Body Lotion (1600)

Step 1 - Generate Content:
   email_content_tool("Lavender Body Lotion", "1600", "https://product-image.jpg", "https://shop.com", "SahulatAI SkinCare")
   
   Returns:
   {
     "success": true,
     "email_content": "<!DOCTYPE html><html>...[Dark themed HTML with product]...",
     "email_subject": "✨ Introducing Lavender Body Lotion - Just for 1600!",
     "product_featured": "Lavender Body Lotion",
     "ready_for_approval": true
   }

Step 2 - Get Approval:
   get_email_design_approval_tool(
     email_content,  // HTML from step 1
     email_subject,  // Subject from step 1
     "owner@business.com"
   )
   
   Result: Owner receives email with:
   - Blue approval instructions banner at top
   - Full campaign preview (dark theme with product image, price, button)
   - Reply options: "APPROVED" or "CANCEL"

Step 3 - Send Campaign (after owner replies "APPROVED"):
   send_emails_tool(
     email_content,  // Same HTML from step 1
     email_subject,  // Same subject from step 1
     "business@gmail.com",
     "Lavender Launch Campaign",
     false  // Not test mode, send to all customers
   )
   
   Returns:
   {
     "success": true,
     "emails_sent": 47,
     "failed_emails": 0,
     "campaign_id": "CAMP_1731334567",
     "total_customers": 47,
     "delivery_status": "completed",
     "message": "Successfully sent ✨ Introducing Lavender Body Lotion - Just for 1600! to 47 customers!"
   }
```

## ⚙️ **Email Marketing Setup Requirements**

### **Environment Configuration:**
```env
# Gmail configuration for sending emails
GOOGLE_REFRESH_TOKEN=your_google_refresh_token
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
GMAIL_APP_PASSWORD=your_gmail_app_password

# Existing inventory/orders config
ORDERS_SHEET_ID=your_orders_sheet_id
ORDERS_WORKSHEET_NAME=Orders
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
```

### **Customer Email Requirements:**
Your **orders sheet** must include customer email addresses in any of these column formats:
- `customer_email`, `email`, `customer email`, `Email`, `Customer Email`

**Example Orders Sheet for Email Marketing:**
```
| Order No | Product Name  | Quantity | Customer Name | Customer Email        | Address      | Status    |
|----------|---------------|----------|---------------|-----------------------|--------------|-----------|
| ORD-001  | Face Wash     | 2        | John Doe      | john@email.com        | City ABC     | Delivered |
| ORD-002  | Body Lotion   | 1        | Jane Smith    | jane.smith@gmail.com  | Town XYZ     | Pending   |
| ORD-003  | Facial Serum  | 3        | Bob Johnson   | bob.j@email.com       | Village 123  | Delivered |
```

### **Gmail App Password Setup:**
1. Go to Google Account Settings → Security → 2-Step Verification
2. Scroll to "App passwords" at the bottom
3. Create new app password for "Mail"
4. Copy the 16-character password
5. Add to `.env` file as `GMAIL_APP_PASSWORD`

## 📊 **Email Marketing Features**

### **🎨 Beautiful Dark Theme Design**
- **Modern Dark Aesthetic** - #1a1a1a background with pink (#ff99aa) accents
- **Mobile-Responsive Layout** - Table-based structure, 600px width, works on all devices
- **Email Client Compatible** - Inline CSS styling, no external dependencies
- **Professional Product Display** - Large product images with rounded corners
- **Clear Call-to-Action** - Prominent "Shop Now" button with hover-friendly styling

### **✅ Professional Approval Workflow**
- **Full Campaign Preview** - Owner sees exact email customers will receive
- **Visual Approval System** - Blue header with clear instructions, green markers around preview
- **Simple Reply-Based Approval** - Just reply "APPROVED" or "CANCEL" to the email
- **Pre-Send Quality Control** - Prevents accidental sends, ensures campaign review

### **📈 Robust Campaign Delivery**
- **Automatic Customer Targeting** - Extracts all customer emails from orders sheet
- **Dual Delivery System** - Gmail API primary + SMTP automatic fallback
- **Delivery Statistics** - Real-time success/failure tracking per campaign
- **Test Mode** - Send to yourself first before mass delivery
- **Rate Limiting** - Prevents email service throttling (0.1s delays)
- **Error Recovery** - Automatic SMTP fallback if Gmail API fails per email

### **🛡️ Auto-Fix Technology**
- **HTML Escaping Detection** - Automatically detects JSON escaping issues
- **Intelligent Correction** - Converts escaped characters (`\\n`, `\\t`, `\\"`) to real ones
- **Debug Logging** - Detailed logs show before/after fix samples
- **Seamless Experience** - Works correctly even with improperly formatted input

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

- **🎯 Targeted Campaigns** - Uses real customer data from orders sheet
- **⚡ Rapid Deployment** - Create, approve, and send campaigns in under 5 minutes
- **📱 Mobile-First Design** - Beautiful rendering on all devices and email clients
- **🎨 Professional Aesthetic** - Modern dark theme with elegant pink accents
- **✅ Quality Control** - Built-in approval process prevents accidental sends
- **📊 Performance Tracking** - Delivery statistics and campaign IDs for each send
- **💰 Cost-Effective** - Complete email marketing solution with no monthly fees
- **🛡️ Bulletproof Delivery** - Dual delivery methods ensure maximum deliverability
- **🔧 Auto-Fixing** - Handles common issues automatically without manual intervention

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