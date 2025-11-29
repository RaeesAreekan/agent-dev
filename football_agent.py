import os
import asyncio
from dotenv import load_dotenv
import google.generativeai as genai
from mcp_server_football import (
    get_livescores,
    get_match_preview,
    get_match,
    get_countries,
    get_leagues,
    get_standings
)
import sqlite3

from google.adk.plugins.logging_plugin import LoggingPlugin

from hey_on_call.heyoncall_tool import send_alert
from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.sessions import InMemorySessionService,DatabaseSessionService
from google.adk.apps.app import App,EventsCompactionConfig
from google.adk.runners import Runner
from googlesearch import search
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.agent_tool import AgentTool

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found in environment variables.")

from x_tools import XTools

# Wrappers for async tools to be used by Gemini
async def get_livescores_tool(search_query:str = None):
    """Get current live scores for ongoing matches.
       optionally, You can pass the league name to get the live scores for that league.
    """
    return await get_livescores(search_query)

async def get_match_preview_tool(match_id: int):
    """Get a preview for a specific match.
    Args:
        match_id: The unique identifier for the match.

    Returns:
        A JSON string containing match preview data.
    """
    return await get_match_preview(match_id)

async def get_match_tool(match_id: int):
    """Get detailed information about a specific match.
    Args:
        match_id: The unique identifier for the match.
    """
    return await get_match(match_id)

async def get_countries_tool():
    """Get a list of all available countries.
    
    Returns:
        A JSON string containing a list of all available countries.
    """
    return await get_countries()

async def get_leagues_tool(search_query: str = None):
    """Get a list of all available leagues.
    
    Args:
        search_query: Optional string to filter leagues by name.
    
    Returns:
        A JSON string containing a list of all available leagues.
    """
    return await get_leagues(search_query)

async def get_standings_tool(league_id: int):
    """Get the standings for a specific league.
    Args:
        league_id: The unique identifier for the league.
    
    Returns:
        A JSON string containing the standings for the specified league.
    """
    return await get_standings(league_id)

## Hey on Call alert wrapper
async def send_alert_tool(message: str):
    """Sends an alert via HeyOnCall.
    Args:
        message: The message to send in the alert.
    """
    return await send_alert(message)

def check_data_in_db():
    with sqlite3.connect("agent.db") as conn:
        cursor = conn.cursor()
        res = cursor.execute( "select app_name, session_id, author, content from events")
        rows = res.fetchall()
        for row in rows:
            print(row)

async def main():
    # Initialize XTools
    x_tools = XTools()
    await x_tools.start()

    try:
        # Define X tool wrappers using the initialized instance
        async def create_tweet_tool(text: str, image_path: str = None, video_path: str = None):
            """Create a new tweet.
            Args:
                text: The text content of the tweet.
                image_path: Optional absolute path to an image file.
                video_path: Optional absolute path to a video file.
            """
            return await x_tools.create_tweet(text, image_path, video_path)

        async def get_home_timeline_tool(limit: int = 20):
            """Get the most recent tweets from your home timeline.
            Args:
                limit: Number of tweets to retrieve (max 100).
            """
            return await x_tools.get_home_timeline(limit)

        async def reply_to_tweet_tool(tweet_id: str, text: str, image_path: str = None, video_path: str = None):
            """Reply to a tweet.
            Args:
                tweet_id: The ID of the tweet to reply to.
                text: The text content of the reply.
                image_path: Optional absolute path to an image file.
                video_path: Optional absolute path to a video file.
            """
            return await x_tools.reply_to_tweet(tweet_id, text, image_path, video_path)

        async def delete_tweet_tool(tweet_id: str):
            """Delete a tweet.
            Args:
                tweet_id: The ID of the tweet to delete.
            """
            return await x_tools.delete_tweet(tweet_id)

        # List of tools for Gemini
        retry_config = types.HttpRetryOptions(
            attempts=5,  # Maximum retry attempts
            exp_base=7,  # Delay multiplier
            initial_delay=1,
            http_status_codes=[429, 500, 503, 504]
        )
        model = Gemini(model="gemini-2.5-flash", api_key=GEMINI_API_KEY, retry_config=retry_config)

        google_search_tool = LlmAgent(
            name="google_search_tool",
            model=model,
            instruction="""You are a search agent that can answer questions about the web.
        You can use the following tools to get information about the web.
        You may use multiple tools to get the information you need.""",
            tools=[GoogleSearchTool()],
        )

        tools = [
            AgentTool(agent=google_search_tool),
            FunctionTool(func=get_livescores_tool),
            FunctionTool(func=get_match_preview_tool),
            FunctionTool(func=get_match_tool),
            FunctionTool(func=get_countries_tool),
            FunctionTool(func=get_leagues_tool),
            FunctionTool(func=get_standings_tool),
            FunctionTool(func=send_alert_tool),
            FunctionTool(func=create_tweet_tool),
            FunctionTool(func=get_home_timeline_tool),
            FunctionTool(func=reply_to_tweet_tool),
            FunctionTool(func=delete_tweet_tool)
        ]


        
        football_agent = LlmAgent(
            name="football_agent",
            model=model,
            instruction="""You are a football agent that can answer questions about football.
        You can use the following tools to get information about football.
        You may use multiple tools to get the information you need.
        eg:
        To get standings in a league , first use get_leagues tool to get the league id and then use get_standings tool to get the standings via league 
        id you got from get_leagues tool.
        
        IMPORTANT: If the result of any tool call contains details about "Real Madrid", you MUST use the send_alert_tool to send an alert with the details.
                    The same with if someone ask about Real Madrid , you MUST use the send_alert_tool to send an alert with the details. You should
                    pass the details to the send_alert_tool as string.

        You also have access to Twitter/X tools. You can read your timeline, create tweets, reply to tweets, and delete tweets. Whenever Someone asks
        about real Madrid , send a small tweet using create_tweet_tool to tweet about Real Madrid.I need you to add the following hashtags in all Tweets
        (#HalaMadrid #RealMadrid #MadridFC #LosBlancos #LaLiga #UCL #ChampionsLeague #Barcelona #ElClassico #Mbappe #Bellingham #Vini #Yamal). Add this Hashtag at the end of the tweet.
        Always add the hashtags at the end of the tweet. Leave at least 5 linespace before the hashtags.

        IMPORTANT: You also have access to google_search_tool. You can use it to search the web, when they questions , for which you cannot answer by using other tools mentioned
        """,
            tools=tools
        )

        football_app = App(
            name = "football_app",
            root_agent=football_agent,
            events_compaction_config=EventsCompactionConfig(
                compaction_interval=3,
                overlap_size=1
            ),
            plugins=[LoggingPlugin()]
        )
        # chat = model.start_chat(enable_automatic_function_calling=True)
        # session_service=InMemorySessionService()
        db_url = "sqlite+aiosqlite:///agent.db"
        session_service = DatabaseSessionService(db_url=db_url)
        runner = Runner(app=football_app, session_service=session_service)

        print("--------------------------------------------------")
        print("Football Agent Started")
        print("Ask me about live scores, matches, leagues, etc.")
        print("Type 'exit' or 'quit' to stop.")
        print("--------------------------------------------------")


        while True:
            try:
                user_input = await asyncio.to_thread(input, "You: ")
                if user_input.lower() in ['exit', 'quit']:
                    break
                
                if not user_input.strip():
                    continue

                try:
                    session = await session_service.create_session(
                        app_name="football_app", user_id="raees", session_id="football_agent_2"
                    )
                except:
                    session = await session_service.get_session(
                        app_name="football_app", user_id="raees", session_id="football_agent_2"
                    )
                query = types.Content(role='user', parts = [types.Part(text=user_input)])
                
                async for event in runner.run_async(user_id = 'raees' , session_id = session.id , new_message=query):
                    if event.content and event.content.parts and event.content.parts[0].text:
                        print("Agent: ", event.content.parts[0].text)
                    

            except Exception as e:
                print(f"An error occurred: {e}")

    finally:
        await x_tools.stop()


if __name__ == "__main__":
    asyncio.run(main())
    check_data_in_db()
