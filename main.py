# server.py
from mcp.server.fastmcp import FastMCP
import os
from datetime import datetime

# Create an MCP server
mcp = FastMCP("Demo")

# Add ASCII rabbit drawing tool
@mcp.tool()
def draw_ascii_rabbit() -> str:
    """Draw a cute ASCII rabbit"""
    rabbit = """
       /|   /|  
      ( :v:  )
       |(_)|
      /     \\
     /       \\
    /         \\
   (___________)
        
    (\   /)
   ( ._. )
  o_(")(")
  
   Or this one:
   
      /|      /|
     (  :v:  )
      )   (
     (  v  )
    ^^  o  ^^
    """
    return rabbit

# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"

# Add a bad joke resource from Dino
@mcp.resource("joke://dino")
def get_dino_joke() -> str:
    """Get a bad joke from Dino"""
    return "Why don't dinosaurs ever pay their bills? Because they're dead broke! 🦕"

NOTES_FILE = os.path.join(os.path.dirname(__file__), "notes.txt")

def ensure_file():
    if not os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "w") as f:
            f.write("")

@mcp.tool()
def add_note(message: str) -> str:
    """
    Append a new note to the sticky note file.

    Args:
        message (str): The note content to be added.

    Returns:
        str: Confirmation message indicating the note was saved.
    """
    ensure_file()
    with open(NOTES_FILE, "a") as f:
        f.write(message + "\n")
    return "Note saved!"

@mcp.tool()
def read_notes() -> str:
    """
    Read and return all notes from the sticky note file.

    Returns:
        str: All notes as a single string separated by line breaks.
             If no notes exist, a default message is returned.
    """
    ensure_file()
    with open(NOTES_FILE, "r") as f:
        content = f.read().strip()
    return content or "No notes yet."

@mcp.resource("notes://latest")
def get_latest_note() -> str:
    """
    Get the most recently added note from the sticky note file.

    Returns:
        str: The last note entry. If no notes exist, a default message is returned.
    """
    ensure_file()
    with open(NOTES_FILE, "r") as f:
        lines = f.readlines()
    return lines[-1].strip() if lines else "No notes yet."

@mcp.prompt()
def note_summary_prompt() -> str:
    """
    Generate a prompt asking the AI to summarize all current notes.

    Returns:
        str: A prompt string that includes all notes and asks for a summary.
             If no notes exist, a message will be shown indicating that.
    """
    ensure_file()
    with open(NOTES_FILE, "r") as f:
        content = f.read().strip()
    if not content:
        return "There are no notes yet."

    return f"Summarize the current notes: {content}"

if __name__ == "__main__":
    # Run the FastMCP server
    mcp.run(transport="stdio")