from agents import Agent, Runner, SQLiteSession
from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter
from agents.model_settings import ModelSettings
from dotenv import load_dotenv
import os

session = SQLiteSession(session_id="quickbooks-gpt5-mini")  # Changed session ID to clear cache

load_dotenv()

AGENT_INSTRUCTIONS = """
You are a smart QuickBooks sales analytics assistant for business owners.
Your job is to provide accurate, actionable insights about their business sales and revenue using QuickBooks data.
Make sure you use your tools correctly and intelligently to answer business questions.
You might get some complex queries for analytics and to answer those, you might need to use multiple tools to get the full answer so use multiple tool calls as needed as per the situation and query.

You have access to the following 4 core tools:
1. search_invoices: Use this tool to get invoice data, sales revenue, payment status, and transaction details
2. search_customers: Use this tool to get customer information, active customer counts, and customer balances
3. search_estimates: Use this tool to get quote/estimate data, pending proposals, and sales pipeline information
4. read_invoice: Use this tool to get detailed line-item breakdown for a specific invoice (requires invoice_id)

CRITICAL RULE: All search tools require a "criteria" parameter that MUST BE AN ARRAY (not an object).
- Correct: {"criteria": []}
- Correct: {"criteria": [{"field": "Active", "value": true, "operator": "="}]}
- WRONG: {"criteria": {}}

When answering business owner questions, use these tool mappings:
These questions are just for you to understand which tool to use based on the query and what type of queries you could get.

SALES VOLUME & REVENUE QUESTIONS:
- "How many sales did we have [today/this week/this month]?" → search_invoices with TxnDate filter, use count parameter or count results
- "How much did we earn [period]?" → search_invoices with TxnDate filter, sum all TotalAmt values
- "What's our total revenue?" → search_invoices with date range, sum TotalAmt
- "How many invoices were created [period]?" → search_invoices with TxnDate filter, count results

CUSTOMER ANALYTICS QUESTIONS:
- "How many active customers do we have?" → search_customers with Active=true, use count parameter
- "Which customers owe us money?" → search_invoices with Balance > 0, group by CustomerRef
- "Who hasn't paid us?" → search_invoices with Balance > 0, sort by DueDate
- "Which customers are the most buyers?" → search_invoices, group by CustomerRef, count invoices per customer
- "What's our average revenue per customer?" → search_invoices (sum TotalAmt) / search_customers (count active)

PRODUCT/SERVICE PERFORMANCE QUESTIONS:
- "What items are sold the most?" → search_invoices, then read_invoice for line items, count item occurrences
- "What are our best-selling products/services?" → search_invoices, aggregate line items from multiple invoices
- "Which items generate the most revenue?" → read_invoice for each invoice, sum amounts by item
- "What's the average quantity sold per item?" → Aggregate line item quantities across invoices

PIPELINE & ESTIMATES QUESTIONS:
- "How many pending quotes do we have?" → search_estimates with TxnStatus="Pending"
- "What's our sales pipeline value?" → search_estimates with TxnStatus="Pending", sum TotalAmt

IMPORTANT TOOL USAGE RULES:
1. Always include "criteria" parameter in search tools, even if empty array []
2. For date filters, use format: {"field": "TxnDate", "value": "2025-11-13", "operator": ">="}
3. For today's date, use 2025-11-13 (current date)
4. Use "count": true parameter when you only need the count, not full data
5. Use "limit" parameter to control result size and improve performance
6. Multiple criteria filters go in an array: [{"field": "...", "value": "...", "operator": "..."}, {...}]
7. For line-item analysis, you must call read_invoice for each invoice to get product details

CALCULATION GUIDELINES:
- Total revenue = Sum of all TotalAmt from invoices
- Unpaid amount = Sum of all Balance from invoices where Balance > 0
- Sales count = Count of invoice results
- Average sale = Total revenue / Sales count
- Items sold = Aggregate quantities from invoice line items

Always provide clear, numerical answers with context. Format currency values with $ sign and two decimal places.
        """

async def run(server: MCPServerStreamableHttp):

    # Try to explicitly set the model in the Agent constructor
    quickbooks_agent = Agent(
        name="QuickBooks Analytics Agent",
        instructions=AGENT_INSTRUCTIONS,
        mcp_servers=[server],
        model="gpt-5-mini",  # Try setting model directly instead of via ModelSettings
    )

    while True:
        user_query = input("\n===  What would you like to know about your business?: ")

        try:
            result = await Runner.run(starting_agent=quickbooks_agent, input=user_query, session=session)
            
            # Extract tool calls from new_items
            tools_used = set()
            for item in result.new_items:
                if hasattr(item, 'type') and item.type == 'tool_call_item':
                    # Check what's in raw_item
                    if hasattr(item, 'raw_item'):
                        raw = item.raw_item
                        # print(f"[DEBUG] raw_item type: {type(raw)}")
                        # print(f"[DEBUG] raw_item attributes: {[a for a in dir(raw) if not a.startswith('_')]}")
                        
                        # Try different possible attribute names
                        if hasattr(raw, 'tool_name'):
                            tools_used.add(raw.tool_name)
                        elif hasattr(raw, 'name'):
                            tools_used.add(raw.name)
                        elif hasattr(raw, 'function') and hasattr(raw.function, 'name'):
                            tools_used.add(raw.function.name)
            
            # Print tools used
            if tools_used:
                print("\n🔧 Tools Used:")
                for tool in sorted(tools_used):
                    print(f"   ✓ {tool}")
            
            print("\n ===== Response: ", result.final_output)
        except Exception as e:
            error_str = str(e)
            print(f"[DEBUG] Error type: {type(e).__name__}")
            print(f"[DEBUG] Error message: {error_str}")

async def main():
    try:
        print("Attempting to start MCP server...")

        headers = {
            "Authorization": f"Bearer {os.getenv('QUICKBOOKS_ACCESS_TOKEN')}",
            "Content-Type": "application/json",
            "X-Access-Token": os.getenv('QUICKBOOKS_ACCESS_TOKEN'),
            "X-Refresh-Token": os.getenv('QUICKBOOKS_REFRESH_TOKEN'),
            "X-Realm-Id": os.getenv('QUICKBOOKS_REALM_ID'),
            "Accept": "application/json"
        }

        async with MCPServerStreamableHttp(
            name = "QuickBooks Analytics Server",
            params= {
                "url" : "https://qb-mcp-server-4a12c03b6a64.herokuapp.com/mcp",
                "headers": headers,
                "timeout" : 10
            },
            tool_filter=create_static_tool_filter(
                allowed_tool_names=["search_invoices", "search_customers", "search_estimates", "read_invoice"]
            ),
            cache_tools_list=True,
        ) as server :
            print("✅ QuickBooks MCP server started successfully!")
            print("✅ Only 4 analytics tools will be loaded: search_invoices, search_customers, search_estimates, read_invoice")
            await run(server)
    except Exception as e:
        print(f"❌ Error initializing MCP server: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())