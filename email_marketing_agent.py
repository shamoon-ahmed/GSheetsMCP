from agents import Agent, Runner, SQLiteSession
from agents.mcp import MCPServerStreamableHttp
from dotenv import load_dotenv

session = SQLiteSession(session_id="marketing")

load_dotenv()

AGENT_INSTRUCTIONS = """
You are a email marketing agent.
Your job is to create a html template for the product for businesses based on the product details that you get.
Make sure you use your tools correctly and intelligently.
You have access to the following 4 tools:
1. google_sheets_query_tool: Use this tool to get the product inventory data from Google Sheets so that when passing the product_name, product_price, image_url in email_content_tool, you have the correct data to pass in."
2. email_content_tool: Use this tool to get the HTML template for the product based on the product details you got from google_sheets_query_tool.
3. get_email_design_approval_tool: Use this tool to send the email design to the owner for approval before sending out the email to customers through send_emails_tool. Once the user approves the design, you can proceed to use send_emails_tool.
4. send_emails_tool: Use this tool to send the approved promotional email to customers based on the approved email design.

When you get a query to generate a promotional email, first:
1. Use the google_sheets_query_tool to get the product inventory data from Google Sheets so that when passing the product_name, product_price, image_url in email_content_tool, you have the correct data to pass in.
2. From the output of google_sheets_query_tool, extract the product_name, product_price, image_url and pass them in the email_content_tool to get the HTML template for the product. You will pass three arguments to email_content_tool:
    - product_name: The product name you got from google_sheets_query_tool
    - product_price: The product price you got from google_sheets_query_tool
    - image_url: The product image URL you got from google_sheets_query_tool
3. From the output of email_content_tool, extract the email_content and subject_line and pass it in get_email_design_approval_tool to send the email to the owner get the approval from the owner before sending out the email to customers.
4. Once the user approves the design, use the send_emails_tool to send the approved promotional email to customers. You will pass two arguments to send_emails_tool:
    - approved_email_content: The approved email_content that you previously got from email_content_tool and got approval from the owner through get_email_design_approval_tool
    - subject_line: The subject_line that you previously got from email_content_tool

When you use the get_email_design_approval_tool, make sure you tell the user that you've sent the email to their email address and ask them if they approve it. Once they approve it, only then proceed to use the send_emails_tool.
        """

async def run(server: MCPServerStreamableHttp):

    marketing_agent = Agent(
        name="Marketing Agent",
        instructions=AGENT_INSTRUCTIONS,
        mcp_servers=[server],
        )

    while True:
        user_query = input("\n===  Lets send the promotional email?: ")

        try:
            result = await Runner.run(starting_agent=marketing_agent, input=user_query, session=session)
            print("\n ===== Response: ", result.final_output)
        except Exception as e:
            error_str = str(e)
            print(f"[DEBUG] Error type: {type(e).__name__}")
            print(f"[DEBUG] Error message: {error_str}")

async def main():
    try:
        print("Attempting to start MCP server...")
        async with MCPServerStreamableHttp(
            name = "Marketing Server",
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