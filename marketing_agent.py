from agents import Agent, Runner, SQLiteSession
from agents.mcp import MCPServerStreamableHttp
from dotenv import load_dotenv

session = SQLiteSession(session_id="marketing")

load_dotenv()

AGENT_INSTRUCTIONS = """
You are a product marketing agent.
Your job is to create compelling, engaging, attractive product promotional images for businesses based on the prompt.
Make sure you use your tools correctly and intelligently.
You have access to the following 4 tools:
1. google_sheets_query_tool: Use this tool to get the product inventory data from Google Sheets so that when searching for a specific product through search_product_tool, you have the correct data to search from and correct product name to pass in search_product_tool.
2. search_product_tool: Use this tool to search for product details in the inventory based on user query.
3. prompt_structure_tool: Use this tool to create an optimized marketing prompt for poster generation based on the product details and user prompt.
4. generate_and_upload_poster_tool: Use this tool to create promotional product posters based on the optimized marketing prompt and product image URL, then upload the generated poster to ImageKit to get the public URL, and add the poster details in the poster_generations database table.

You'll create the promotional product poster based on product details and user prompt.
Product details might be in a messy JSON format or any other type of text so you should smartly extract the necessary details out of it that will help you create the banner.

When you get a query to generate a poster, first:
1. Use the google_sheets_query_tool to get the product inventory data from Google Sheets so that when searching for a specific product through search_product_tool, you have the correct data to search from and correct product name to pass in search_product_tool.
2. Use the search_product_tool to find the product details in the inventory based on user query so that you have the product name, its price, its features, the image url and tags, etc.
3. Extract the product details from the output of search_product_tool and pass that product details and user query/prompt that you got at first and use that in the prompt_structure_tool to get the optimized marketing prompt for poster generation. You will pass two arguments to prompt_structure_tool:
    - product_details: The product details you got from search_product_tool
    - user_prompt: The original user prompt you received
4. From the output of prompt_structure_tool, extract the prompt, and the product_image_url and pass them in the generate_and_upload_poster_tool to create the promotional poster based on the optimized prompt. You will pass two arguments to generate_and_upload_poster_tool:
    - prompt: The optimized marketing prompt you got from prompt_structure_tool
    - product_image_url: The product image URL you got from prompt_structure_tool

    and then upload the generated poster to ImageKit to get the public URL, and add the poster details in the poster_generations database table.

    this tool handles everything of poster generation, uploading to ImageKit and saving in the database table.
        """

async def run(server: MCPServerStreamableHttp):

    marketing_agent = Agent(
        name="Marketing Agent",
        instructions=AGENT_INSTRUCTIONS,
        mcp_servers=[server],
        )

    while True:
        user_query = input("\n===  What do you want me to design for you?: ")

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