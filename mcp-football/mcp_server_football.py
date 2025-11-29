from mcp.server.fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("soccer-data")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Configuration
API_END_POINT = "https://api.soccerdataapi.com/"
# User can set this in their environment or .env file
AUTH_KEY = os.environ.get("AUTH_KEY") or "YOUR_API_KEY_HERE"

async def _make_request(endpoint: str, params: dict = None) -> str:
    """Helper function to make requests to the Soccer Data API."""
    if not AUTH_KEY:
        return "Error: AUTH_KEY is not set. Please set the AUTH_KEY environment variable."

    url = f"{API_END_POINT}{endpoint}"
    final_params = {"auth_token": AUTH_KEY}
    if params:
        final_params.update(params)
    logger.info(f"Making request to {url} with params {final_params}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url,
                params=final_params,
                headers={
                    "Content-Type": "application/json",
                    "Accept-Encoding": "gzip",
                },
                timeout=15.0
            )
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            return f"API Error: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"Request Error: {str(e)}"

@mcp.tool()
async def get_livescores(search_term: str = None) -> str:
    """
    Get current live scores for ongoing matches.
    Returns a JSON string containing live score data.
    Optionally , one can search matches by League Name. We will return the match match id , home team name and away team name along with their ids.
    You can use the match id , to get match details via , get_match_preview or get_match tool.
    """
    response = await _make_request("livescores/")
    
    if not search_term:
        return response
    
    try:
        data = json.loads(response)
        if "results" not in data:
            return response
            
        filtered_results = []
        
        for league in data["results"]:
            league_name = (league.get("league_name") or "").lower()
            if search_term.lower() not in league_name:
                continue

            league_id = league.get("league_id")
            # `stage` is expected to be a list
            for stage in league.get("stage", []):
                stage_id = stage.get("stage_id")
                stage_name = stage.get("stage_name")

                # `matches` is a list
                for match in stage.get("matches", []):
                    try:
                        match_id = match.get("id")
                        teams = match.get("teams", {})
                        home = teams.get("home") or {}
                        away = teams.get("away") or {}

                        # Collect fields defensively
                        entry = {
                            "id": match_id,
                            "league_id": league_id,
                            "league_name": league.get("league_name"),
                            "stage_id": stage_id,
                            "stage_name": stage_name,
                            "home_team_id": home.get("id"),
                            "home_team": home.get("name"),
                            "away_team_id": away.get("id"),
                            "away_team": away.get("name"),
                            "status": match.get("status"),
                            "date": match.get("date"),
                            "time": match.get("time")
                        }
                        filtered_results.append(entry)
                    except Exception as inner_e:
                        # don't fail the whole loop for one bad match object
                        logger.exception("Error parsing a match object; skipping it.")
                        continue
        
        return json.dumps({"count": len(filtered_results), "results": filtered_results}, indent=2)
    except Exception as e:
        return f"Error processing matches: {str(e)}"
@mcp.tool()
async def get_match_preview(match_id: int) -> str:
    """
    Get a preview for a specific match.
    
    Args:
        match_id: The unique identifier for the match.
    """
    return await _make_request("match-preview/", {"match_id": match_id})

@mcp.tool()
async def get_match(match_id: int) -> str:
    """
    Get detailed information about a specific match.
    
    Args:
        match_id: The unique identifier for the match.
    """
    return await _make_request("match/", {"match_id": match_id})

@mcp.tool()
async def get_countries() -> str:
    """
    Get a list of all available countries.
    """
    return await _make_request("country/")

import json

@mcp.tool()
async def get_leagues(search_query: str = None) -> str:
    """
    Get a list of all available leagues.
    Optionally , one can search for a specific league by name.
    One needs to pass down a search_query to get the filtered results.
    Args:
        search_query: Optional string to filter leagues by name.
    """
    response = await _make_request("league/")
    
    if not search_query:
        return response
        
    try:
        data = json.loads(response)
        if "results" not in data:
            return response
            
        filtered_results = []
        
        for league in data["results"]:
            if search_query in league.get("name", "").lower():
                filtered_results.append({
                    "id": league.get("id"),
                    "name": league.get("name"),
                    "country": league.get("country", {}).get("name")
                })
                
        return json.dumps({"count": len(filtered_results), "results": filtered_results}, indent=2)
    except Exception as e:
        return f"Error processing leagues: {str(e)}"

@mcp.tool()
async def get_standings(league_id: int) -> str:
    """
    Get the standings for a specific league.
    
    Args:
        league_id: The unique identifier for the league.
    """
    return await _make_request("standing/", {"league_id": league_id})

if __name__ == "__main__":
    mcp.run()
