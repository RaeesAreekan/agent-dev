import asyncio
import os
from contextlib import AsyncExitStack
from typing import Optional, Dict, Any, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class XTools:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self._server_params = None

    async def start(self):
        """Starts the MCP server and initializes the session."""
        # Define server parameters
        # We assume 'node' is in the PATH.
        # The script path is relative to the agent_dev directory or absolute.
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "x-mcp-server", "build", "index.js"))
        cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), "x-mcp-server"))
        
        env = os.environ.copy()
        
        self._server_params = StdioServerParameters(
            command="node",
            args=[script_path],
            cwd=cwd,
            env=env
        )

        # Connect to the server
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(self._server_params))
        self.read, self.write = stdio_transport
        
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.read, self.write))
        await self.session.initialize()
        
    async def stop(self):
        """Stops the session and server."""
        await self.exit_stack.aclose()

    async def create_tweet(self, text: str, image_path: Optional[str] = None, video_path: Optional[str] = None) -> str:
        """Create a new tweet with optional image or video attachment.
        
        Args:
            text: The text content of the tweet.
            image_path: Optional absolute path to an image file.
            video_path: Optional absolute path to a video file.
        """
        if not self.session:
            raise RuntimeError("XTools session not started")

        arguments = {"text": text}
        if image_path:
            arguments["image_path"] = image_path
        if video_path:
            arguments["video_path"] = video_path

        result = await self.session.call_tool("create_tweet", arguments=arguments)
        return result.content[0].text

    async def get_home_timeline(self, limit: int = 20) -> str:
        """Get the most recent tweets from your home timeline.
        
        Args:
            limit: Number of tweets to retrieve (max 100).
        """
        if not self.session:
            raise RuntimeError("XTools session not started")

        result = await self.session.call_tool("get_home_timeline", arguments={"limit": limit})
        return result.content[0].text

    async def reply_to_tweet(self, tweet_id: str, text: str, image_path: Optional[str] = None, video_path: Optional[str] = None) -> str:
        """Reply to a tweet.
        
        Args:
            tweet_id: The ID of the tweet to reply to.
            text: The text content of the reply.
        """
        if not self.session:
            raise RuntimeError("XTools session not started")

        arguments = {"tweet_id": tweet_id, "text": text}
        if image_path:
            arguments["image_path"] = image_path
        if video_path:
            arguments["video_path"] = video_path

        result = await self.session.call_tool("reply_to_tweet", arguments=arguments)
        return result.content[0].text

    async def delete_tweet(self, tweet_id: str) -> str:
        """Delete a tweet.
        
        Args:
            tweet_id: The ID of the tweet to delete.
        """
        if not self.session:
            raise RuntimeError("XTools session not started")

        result = await self.session.call_tool("delete_tweet", arguments={"tweet_id": tweet_id})
        return result.content[0].text
