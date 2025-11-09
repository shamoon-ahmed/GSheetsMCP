from agents import Agent, Runner, SQLiteSession
from agents.mcp import MCPServerStreamableHttp
from dotenv import load_dotenv

session = SQLiteSession(session_id="marketing")

load_dotenv()

AGENT_INSTRUCTIONS = """
You are a product marketing agent.
Your job is to create compelling, engaging, attractive product promotional images for businesses based on the prompt.
Make sure you use your tools correctly and intelligently.
You have access to the following tools:
1. search_product_tool: Use this tool to search for product details in the inventory based on user query.
2. prompt_structure_tool: Use this tool to get the optimized marketing prompt for generating the poster
3. generate_images_tool: Use this tool to create the promotional poster based on the optimized prompt

You'll create the promotional product poster based on product details and user prompt.
Product details might be in a messy JSON format or any other type of text so you should smartly extract the necessary details out of it that will help you create the banner.

When you get a query to generate a poster, first:
1. Use the search_product_tool to find the product details in the inventory based on user query so that you have the product name, its price, its features, the image url and tags, etc.
2. Extract the product details from the output of search_product_tool and pass that product details and user query/prompt that you got at first and use that in the prompt_structure_tool to get the optimized marketing prompt for poster generation. You will pass two arguments to prompt_structure_tool:
    - product_details: The product details you got from search_product_tool
    - user_prompt: The original user prompt you received
3. From the output of prompt_structure_tool, extract the prompt, and the product_image_url and pass them in the generate_images_tool to create the promotional poster based on the optimized prompt. You will pass two arguments to generate_images_tool:
    - prompt: The optimized marketing prompt you got from prompt_structure_tool
    - product_image_url: The product image URL you got from prompt_structure_tool
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