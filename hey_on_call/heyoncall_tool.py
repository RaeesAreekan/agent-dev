import httpx
import logging
from dotenv import load_dotenv
import os

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_alert(message: str) -> str:
    """
    Sends an alert via HeyOnCall.
    
    Args:
        message: The message to send in the alert.
    """
    url = f"https://api.heyoncall.com/triggers/{os.getenv('HEYONCALL_TRIGGER_ID')}/mcp"
    headers = {
        "Authorization": f"Bearer {os.getenv('HEYONCALL_AUTH_KEY')}",
        "Content-Type": "application/json"
    }
    # The payload might need to be adjusted based on what HeyOnCall expects.
    # Based on the user description, it seems it might just be a trigger, but passing data is usually good.
    # The curl command didn't show a body, but usually alerts have some content.
    # Let's assume we can pass a 'message' or similar. 
    # However, the user provided curl command was:
    # mcp add ... "HeyOnCall" ...
    # And the JSON config.
    # The curl command implies it's a GET or POST. Let's try POST with a body if message is provided.
    # If the user just wants to trigger it, maybe the body isn't strictly required or is specific.
    # Let's try sending the message in the body.
    
    # The server is an MCP server accepting JSON-RPC via POST.
    # Tool name: HeyOnCall__set_alerting
    # Arguments: payload: { message: ... }
    
    json_rpc_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "HeyOnCall__set_alerting",
            "arguments": {
                "payload": {
                    "message": message
                }
            }
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Sending alert to HeyOnCall: {message}")
            response = await client.post(url, headers=headers, json=json_rpc_payload, timeout=10.0)
            response.raise_for_status()
            
            # Check for JSON-RPC errors in response
            response_data = response.json()
            if "error" in response_data:
                logger.error(f"JSON-RPC error: {response_data['error']}")
                return f"Error sending alert: {response_data['error']}"
            
            return f"Alert sent successfully. Response: {response_data}"
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error sending alert: {e.response.text}")
            return f"Failed to send alert: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            return f"Error sending alert: {str(e)}"
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error sending alert: {e.response.text}")
            return f"Failed to send alert: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            return f"Error sending alert: {str(e)}"
