import asyncio
import json
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncAzureOpenAI

# Load environment variables
load_dotenv(".env")


class MCPAzureOpenAIClient:
    """Client for interacting with Azure OpenAI models using MCP tools."""

    def __init__(self, deployment_name: str = None):
        """Initialize the Azure OpenAI MCP client.

        Args:
            deployment_name: The Azure OpenAI deployment name. If not provided, will use environment variable.
        """
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
        # Azure OpenAI configuration
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01")
        self.deployment_name = deployment_name or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        
        if not all([api_key, endpoint, self.deployment_name]):
            raise ValueError(
                "Missing required Azure OpenAI configuration. Please set AZURE_OPENAI_API_KEY, "
                "AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT_NAME in your .env file."
            )
        
        self.openai_client = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )
        
        self.stdio: Optional[Any] = None
        self.write: Optional[Any] = None

    async def connect_to_server(self, server_script_path: str = "main.py"):
        """Connect to an MCP server.

        Args:
            server_script_path: Path to the server script.
        """
        # Server configuration
        server_params = StdioServerParameters(
            command="python",
            args=[server_script_path],
        )

        # Connect to the server
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        # Initialize the connection
        await self.session.initialize()        # List available tools
        tools_result = await self.session.list_tools()
        
        print("\nConnected to server with tools:")
        for tool in tools_result.tools:
            print(f"  - {tool.name}: {tool.description}")
    
    async def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """Get available tools from the MCP server in OpenAI format.

        Returns:
            A list of tools in OpenAI format.
        """
        tools_result = await self.session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
            for tool in tools_result.tools
        ]
    
    async def process_query(self, query: str) -> str:
        """Process a query using Azure OpenAI and available MCP tools.

        Args:
            query: The user query.

        Returns:
            The response from Azure OpenAI.
        """
        # Get available tools
        tools = await self.get_mcp_tools()

        try:
            # Initial Azure OpenAI API call
            response = await self.openai_client.chat.completions.create(
                model=self.deployment_name,  # Use deployment name instead of model for Azure
                messages=[{"role": "user", "content": query}],
                tools=tools,
                tool_choice="auto",
            )
        except Exception as e:
            print(f"Error calling Azure OpenAI: {e}")
            print(f"Deployment name used: {self.deployment_name}")
            print("Please check your Azure OpenAI configuration:")
            print("- AZURE_OPENAI_ENDPOINT should be: https://your-resource-name.openai.azure.com/")
            print("- AZURE_OPENAI_DEPLOYMENT_NAME should match your model deployment name in Azure")
            print("- Make sure your deployment is active and the model is deployed")
            raise        # Get assistant's response
        assistant_message = response.choices[0].message

        # Initialize conversation with user query and assistant response
        assistant_msg = {
            "role": "assistant",
        }
        
        # Ensure content is always a string (Azure OpenAI requirement)
        if assistant_message.content:
            assistant_msg["content"] = assistant_message.content
        else:
            assistant_msg["content"] = ""
        
        # Only add tool_calls if they exist and are not None
        if assistant_message.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in assistant_message.tool_calls
            ]
            
        messages = [
            {"role": "user", "content": query},
            assistant_msg
        ]

        # Handle tool calls if present
        if assistant_message.tool_calls:
            # Process each tool call
            for tool_call in assistant_message.tool_calls:
                # Execute tool call
                result = await self.session.call_tool(
                    tool_call.function.name,
                    arguments=json.loads(tool_call.function.arguments),
                )                # Add tool response to conversation
                tool_content = ""
                if result.content:
                    if isinstance(result.content, list) and len(result.content) > 0:
                        tool_content = str(result.content[0].text)
                    else:
                        tool_content = str(result.content)
                
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_content,
                    }
                )

            # Get final response from Azure OpenAI with tool results
            final_response = await self.openai_client.chat.completions.create(
                model=self.deployment_name,  # Use deployment name instead of model for Azure
                messages=messages,
                tools=tools,
                tool_choice="none",  # Don't allow more tool calls
            )

            return final_response.choices[0].message.content

        # No tool calls, just return the direct response
        return assistant_message.content

    async def cleanup(self):
        """Clean up resources."""
        await self.exit_stack.aclose()



async def interactive_azure_openai():
    """Interactive Azure OpenAI client with MCP tools."""
    client = MCPAzureOpenAIClient()
    try:
        await client.connect_to_server("main.py")

        print("\n" + "="*60)
        print("🤖 Azure OpenAI + MCP Interactive Client")
        print("Type your questions or requests. Type 'exit' to quit.")
        print("="*60)

        while True:
            try:
                # Get user input
                user_input = input("\n💬 You: ").strip()
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("👋 Goodbye!")
                    break
                elif user_input == "":
                    print("⚠️  Please enter a question or request.")
                    continue
                
                print(f"🔄 Processing: {user_input}")
                
                # Process the query
                response = await client.process_query(user_input)
                print(f"\n🤖 Assistant: {response}")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error processing query: {e}")
                
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("Please update your .env file with the correct Azure OpenAI settings.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await client.cleanup()


async def main():
    """Main entry point for Azure OpenAI integration."""
    await interactive_azure_openai()


if __name__ == "__main__":
    asyncio.run(main())