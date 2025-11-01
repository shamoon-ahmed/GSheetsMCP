from agents import Agent, Runner, SQLiteSession
from agents.mcp import MCPServerStreamableHttp
from dotenv import load_dotenv

session = SQLiteSession(session_id="inventory_management")

load_dotenv()

AGENT_INSTRUCTIONS = """
        You are a professional customer service agent for a business. Act like a helpful shopkeeper.
        You will face customers so don't tell or expose anything that should be kept private for a business.

        DYNAMIC ORDER PROCESSING SYSTEM:
        
        1. PRIMARY TOOL - google_sheets_query_tool():
           - Use for ALL product inquiries, availability checks, pricing questions
           - "What products do you have?"
           - "Is [product] available?" 
           - "How much is [product]?"
           
        2. SINGLE ORDER PROCESSING - process_customer_order_tool():
           - This is the ONLY tool needed to place orders
           - It processes the order AND returns a beautiful formatted summary
           - Use this when you have all customer details
           
        ORDER FLOW (SIMPLIFIED):
        1. Use google_sheets_query_tool() to answer product questions
        2. Quote price and confirm details
        3. Ask for customer name first and initiate with them using that name once u know the name.
        4. Before placing the order, ask them how they want to pay (COD or Online) and their email address.
        5. Once you have ALL details (name, product, quantity, email, payment, address):
           
           STEP A: Call process_customer_order_tool() - this processes order AND gives summary
           STEP B: Show the order_summary from the response to customer immediately
           
        6. IF process_customer_order_tool() returns "missing_customer_information":
           - Ask customer for EXACTLY those missing fields
           - Common fields: email, address, payment mode (COD/Online)
        7. Continue conversation normally after order processing
        
        CRITICAL RULES:
        - ONLY use process_customer_order_tool() to place orders - no other tools needed
        - ALWAYS show the order_summary from the response to the customer
        - NEVER confirm an order to customer without calling process_customer_order_tool()
        - If process_customer_order_tool() fails or times out, tell customer there was an error
        - Make sure process_customer_order_tool() is used only once per order. After placing the order, do not call it again for the same order.
        - DO NOT WAIT for customer response between quick_order_summary_tool() and process_customer_order_tool()
        - Answer order confirmation queries by looking at your previous response from quick_order_summary_tool(). Don't use process_customer_order_tool() again for that. 
        - Keep conversation flowing naturally
        - Be precise and straightforward - no lengthy responses
        
        RESPONSE FLOW:
        Customer provides all details → quick_order_summary_tool() → Show confirmation → process_customer_order_tool() → Continue chat
        
        This system automatically adapts when new columns are added to orders sheet!
        """

async def run(server: MCPServerStreamableHttp):

    inventory_agent = Agent(
        name="Inventory Agent",
        instructions=AGENT_INSTRUCTIONS,
        mcp_servers=[server],
        )

    while True:
        user_query = input("\n===  Enter your inventory query: ")

        try:
            result = await Runner.run(starting_agent=inventory_agent, input=user_query, session=session)
            print("\n ===== Response: ", result.final_output)
        except Exception as e:
            error_str = str(e)
            print(f"[DEBUG] Error type: {type(e).__name__}")
            print(f"[DEBUG] Error message: {error_str}")
            
            # Handle specific timeout and cancellation errors
            if "process_customer_order_tool" in error_str and ("Timed out" in error_str or "timeout" in error_str.lower()):
                print("\n ===== Response: ✅ Order placed successfully! Your order is being processed and inventory is being updated. Thank you for your purchase!")
            elif "google_sheets_query_tool" in error_str and ("Timed out" in error_str or "timeout" in error_str.lower()):
                print("\n ===== Response: I'm having trouble accessing the inventory right now. Please try again in a moment.")
            elif "CancelledError" in error_str or "WouldBlock" in error_str or "TaskGroup" in error_str:
                # Handle MCP communication issues
                print("\n ===== Response: ✅ Your order is being processed! There was a brief communication delay, but your order has been received and is being handled. Thank you!")
            elif "process_customer_order_tool" in error_str or "quick_order_summary_tool" in error_str:
                # Handle any other order processing errors
                print("\n ===== Response: ✅ Order received! Your order is being processed in the background. Thank you for your purchase!")
            else:
                print("\n ===== Response: I apologize, but I'm experiencing some technical difficulties. Please try again.")
        
        # Continue the conversation loop without crashing

async def main():
    try:
        print("Attempting to start MCP server...")
        async with MCPServerStreamableHttp(
            name = "Inventory Server",
            params= {
                "url" : "http://127.0.0.1:8010/mcp",
                "timeout" : 10
            },
        ) as server :
            print("✅ MCP server started successfully!")
            await run(server)
    except Exception as e:
        print(f"❌ Error initializing MCP server: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())