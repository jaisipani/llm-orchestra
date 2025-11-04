"""
Demo script showing the orchestrator in action.
This simulates the flow without requiring actual API keys.
"""

from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel

console = Console()


# Simulated Intent Model
class Intent(BaseModel):
    intent: str
    parameters: dict
    confidence: float = Field(ge=0.0, le=1.0)


def demo_intent_parsing():
    """Demonstrate how natural language gets parsed into structured intents."""
    
    console.print(Panel.fit(
        "[bold cyan]Demo: Natural Language ? Structured Intent[/bold cyan]",
        border_style="cyan"
    ))
    
    examples = [
        {
            "command": "Send an email to john@example.com about the Q4 meeting",
            "intent": Intent(
                intent="send_email",
                parameters={
                    "to": "john@example.com",
                    "subject": "Q4 meeting",
                    "body": "Hi John,\n\nI wanted to discuss the Q4 meeting with you.\n\nBest regards"
                },
                confidence=0.95
            )
        },
        {
            "command": "Search for emails from sarah@company.com from last week",
            "intent": Intent(
                intent="search_email",
                parameters={
                    "query": "from:sarah@company.com",
                    "after": "2024-01-20"
                },
                confidence=0.92
            )
        },
        {
            "command": "Schedule a team meeting tomorrow at 2pm",
            "intent": Intent(
                intent="create_event",
                parameters={
                    "summary": "Team meeting",
                    "start_time": "2024-01-28T14:00:00",
                    "end_time": "2024-01-28T15:00:00"
                },
                confidence=0.88
            )
        }
    ]
    
    for i, example in enumerate(examples, 1):
        console.print(f"\n[bold yellow]Example {i}:[/bold yellow]")
        console.print(f"[cyan]User says:[/cyan] \"{example['command']}\"")
        console.print(f"\n[green]Parsed Intent:[/green]")
        console.print(f"  Intent: {example['intent'].intent}")
        console.print(f"  Parameters: {example['intent'].parameters}")
        console.print(f"  Confidence: {example['intent'].confidence:.2%}")


def demo_service_structure():
    """Show the clean service structure."""
    
    console.print(Panel.fit(
        "[bold cyan]Demo: Service Layer Architecture[/bold cyan]",
        border_style="cyan"
    ))
    
    console.print("\n[bold green]GmailService Methods:[/bold green]")
    methods = [
        "send_email(to, subject, body, cc=None)",
        "search_emails(query, max_results=10, label_ids=None)",
        "get_email(message_id)",
        "delete_email(message_id)",
        "get_profile()"
    ]
    
    for method in methods:
        console.print(f"  ? {method}")
    
    console.print("\n[bold]Key Features:[/bold]")
    console.print("  ? Type hints everywhere")
    console.print("  ? Comprehensive error handling")
    console.print("  ? Detailed logging")
    console.print("  ? Clean, single-responsibility methods")
    console.print("  ? Docstrings for all public methods")


def demo_code_quality():
    """Demonstrate code quality principles."""
    
    console.print(Panel.fit(
        "[bold cyan]Demo: Code Quality Principles[/bold cyan]",
        border_style="cyan"
    ))
    
    principles = {
        "Type Safety": "Full type hints using Python 3.11+ syntax",
        "Validation": "Pydantic models ensure data integrity",
        "Error Handling": "Try/catch with meaningful messages",
        "Logging": "Structured logging with rich formatting",
        "Modularity": "Each service is independent and testable",
        "Documentation": "Docstrings + inline comments where needed",
        "Configuration": "Environment-based config with Pydantic Settings",
        "Security": "Credentials never in code, OAuth tokens encrypted"
    }
    
    for principle, description in principles.items():
        console.print(f"\n[bold green]{principle}:[/bold green]")
        console.print(f"  {description}")


def demo_workflow():
    """Show a complete workflow."""
    
    console.print(Panel.fit(
        "[bold cyan]Demo: Complete Workflow[/bold cyan]",
        border_style="cyan"
    ))
    
    steps = [
        ("1. User Input", 'User: "Send email to team@company.com about project"', "cyan"),
        ("2. LLM Parsing", "GPT-4 extracts: intent=send_email, to=team@..., subject=project", "yellow"),
        ("3. Validation", "Pydantic validates all required fields present", "green"),
        ("4. Confirmation", "Show preview ? Ask user to confirm", "magenta"),
        ("5. Execution", "GmailService.send_email() called with parameters", "blue"),
        ("6. Result", "? Email sent! Message ID: abc123...", "green")
    ]
    
    for step, description, color in steps:
        console.print(f"\n[bold {color}]{step}[/bold {color}]")
        console.print(f"  {description}")


if __name__ == "__main__":
    console.print("\n[bold magenta]???????????????????????????????????????????????[/bold magenta]")
    console.print("[bold magenta]  Intelligent Orchestrator - Code Demo[/bold magenta]")
    console.print("[bold magenta]???????????????????????????????????????????????[/bold magenta]\n")
    
    demo_intent_parsing()
    console.print("\n" + "?" * 60 + "\n")
    
    demo_service_structure()
    console.print("\n" + "?" * 60 + "\n")
    
    demo_code_quality()
    console.print("\n" + "?" * 60 + "\n")
    
    demo_workflow()
    
    console.print("\n[bold green]? Demo complete![/bold green]")
    console.print("\n[dim]To run the actual orchestrator:[/dim]")
    console.print("[dim]  1. Copy .env.example to .env and add your API keys[/dim]")
    console.print("[dim]  2. Run: python -m src.main --auth[/dim]")
    console.print("[dim]  3. Run: python -m src.main -i[/dim]")
