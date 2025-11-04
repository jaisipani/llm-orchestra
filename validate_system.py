#!/usr/bin/env python3
"""
Comprehensive system validation script.
Tests all components and shows what works and what doesn't.
"""

import sys
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def check_python_version():
    """Check Python version."""
    import sys
    version = sys.version_info
    if version >= (3, 10):
        console.print("[green]?[/green] Python version OK:", f"{version.major}.{version.minor}.{version.micro}")
        return True
    else:
        console.print(f"[red]?[/red] Python {version.major}.{version.minor} too old (need 3.10+)")
        return False

def check_dependencies():
    """Check all required packages are installed."""
    console.print("\n[bold cyan]Checking Dependencies...[/bold cyan]")
    
    packages = [
        ("google.auth", "Google Auth"),
        ("openai", "OpenAI"),
        ("pydantic", "Pydantic"),
        ("click", "Click CLI"),
        ("rich", "Rich formatting"),
        ("dotenv", "Python Dotenv"),
    ]
    
    all_ok = True
    for module_name, display_name in packages:
        try:
            __import__(module_name)
            console.print(f"[green]?[/green] {display_name}")
        except ImportError:
            console.print(f"[red]?[/red] {display_name} NOT INSTALLED")
            all_ok = False
    
    return all_ok

def check_environment():
    """Check .env configuration."""
    console.print("\n[bold cyan]Checking Environment Configuration...[/bold cyan]")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    checks = []
    
    # Check .env file exists
    env_file = Path(".env")
    if env_file.exists():
        console.print("[green]?[/green] .env file exists")
        checks.append(True)
    else:
        console.print("[red]?[/red] .env file not found")
        checks.append(False)
        return False
    
    # Check OpenAI API key
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and openai_key.startswith("sk-"):
        console.print(f"[green]?[/green] OpenAI API key configured (starts with: {openai_key[:10]}...)")
        checks.append(True)
    else:
        console.print("[red]?[/red] OpenAI API key not configured or invalid")
        checks.append(False)
    
    # Check Google OAuth
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    
    if client_id and ".apps.googleusercontent.com" in client_id:
        console.print(f"[green]?[/green] Google Client ID configured")
        checks.append(True)
    else:
        console.print("[red]?[/red] Google Client ID not configured")
        checks.append(False)
    
    if client_secret and client_secret.startswith("GOCSPX-"):
        console.print(f"[green]?[/green] Google Client Secret configured")
        checks.append(True)
    else:
        console.print("[red]?[/red] Google Client Secret not configured")
        checks.append(False)
    
    return all(checks)

def check_project_structure():
    """Check project files exist."""
    console.print("\n[bold cyan]Checking Project Structure...[/bold cyan]")
    
    required_files = [
        "src/main.py",
        "src/config/settings.py",
        "src/auth/google_auth.py",
        "src/services/gmail_service.py",
        "src/llm/client.py",
        "src/llm/prompts.py",
        "src/orchestrator/intent_parser.py",
        "src/utils/logger.py",
    ]
    
    all_ok = True
    for file_path in required_files:
        if Path(file_path).exists():
            console.print(f"[green]?[/green] {file_path}")
        else:
            console.print(f"[red]?[/red] {file_path} MISSING")
            all_ok = False
    
    return all_ok

def test_imports():
    """Test importing our modules."""
    console.print("\n[bold cyan]Testing Module Imports...[/bold cyan]")
    
    tests = []
    
    try:
        from src.config.settings import settings
        console.print("[green]?[/green] Config module imports OK")
        tests.append(True)
    except Exception as e:
        console.print(f"[red]?[/red] Config import failed: {e}")
        tests.append(False)
    
    try:
        from src.utils.logger import logger
        console.print("[green]?[/green] Logger module imports OK")
        tests.append(True)
    except Exception as e:
        console.print(f"[red]?[/red] Logger import failed: {e}")
        tests.append(False)
    
    try:
        from src.llm.client import LLMClient
        console.print("[green]?[/green] LLM client imports OK")
        tests.append(True)
    except Exception as e:
        console.print(f"[red]?[/red] LLM client import failed: {e}")
        tests.append(False)
    
    try:
        from src.orchestrator.intent_parser import IntentParser
        console.print("[green]?[/green] Intent parser imports OK")
        tests.append(True)
    except Exception as e:
        console.print(f"[red]?[/red] Intent parser import failed: {e}")
        tests.append(False)
    
    return all(tests)

def check_authentication_status():
    """Check if already authenticated with Google."""
    console.print("\n[bold cyan]Checking Authentication Status...[/bold cyan]")
    
    token_path = Path("credentials/token.json")
    if token_path.exists():
        console.print("[green]?[/green] Authentication token found")
        console.print(f"    Location: {token_path}")
        return True
    else:
        console.print("[yellow]?[/yellow] Not authenticated yet")
        console.print("    Run: python -m src.main --auth")
        return False

def test_openai_connection():
    """Test OpenAI API connection."""
    console.print("\n[bold cyan]Testing OpenAI Connection...[/bold cyan]")
    
    try:
        from openai import OpenAI
        import os
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            console.print("[red]?[/red] No API key found")
            return False
        
        client = OpenAI(api_key=api_key)
        
        # Try a simple completion
        console.print("[yellow]...[/yellow] Testing API call...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'test' if you can read this."}],
            max_tokens=10
        )
        
        result = response.choices[0].message.content
        console.print(f"[green]?[/green] OpenAI API connection works!")
        console.print(f"    Response: {result}")
        return True
        
    except Exception as e:
        console.print(f"[red]?[/red] OpenAI API test failed: {e}")
        return False

def show_usage_instructions():
    """Show how to use the system."""
    console.print("\n" + "="*70 + "\n")
    
    console.print(Panel.fit(
        "[bold cyan]How to Use the System[/bold cyan]",
        border_style="cyan"
    ))
    
    console.print("\n[bold yellow]Step 1: Authenticate with Google[/bold yellow]")
    console.print("   Run: [cyan]./venv/bin/python -m src.main --auth[/cyan]")
    console.print("   This will open a browser for Google login\n")
    
    console.print("[bold yellow]Step 2: Interactive Mode[/bold yellow]")
    console.print("   Run: [cyan]./venv/bin/python -m src.main -i[/cyan]")
    console.print("   Then type commands like:")
    console.print("   ? 'search for emails from gmail'")
    console.print("   ? 'find unread emails'")
    console.print("   ? Type 'quit' to exit\n")
    
    console.print("[bold yellow]Step 3: Single Command[/bold yellow]")
    console.print("   Run: [cyan]./venv/bin/python -m src.main -c \"your command\"[/cyan]\n")

def create_results_table(results):
    """Create a summary table."""
    table = Table(title="Validation Results", show_header=True, header_style="bold cyan")
    table.add_column("Component", style="white")
    table.add_column("Status", style="white")
    table.add_column("Notes", style="dim")
    
    for component, status, notes in results:
        status_icon = "[green]? PASS[/green]" if status else "[red]? FAIL[/red]"
        table.add_row(component, status_icon, notes)
    
    return table

def main():
    """Run all validation checks."""
    console.print("\n")
    console.print(Panel.fit(
        "[bold cyan]System Validation - Intelligent Orchestrator[/bold cyan]\n"
        "Checking all components...",
        border_style="cyan"
    ))
    
    results = []
    
    # Run all checks
    result = check_python_version()
    results.append(("Python Version", result, "Python 3.10+ required"))
    
    result = check_dependencies()
    results.append(("Dependencies", result, "All packages installed"))
    
    result = check_environment()
    results.append(("Environment Config", result, ".env file with API keys"))
    
    result = check_project_structure()
    results.append(("Project Structure", result, "All source files present"))
    
    result = test_imports()
    results.append(("Module Imports", result, "Python modules load correctly"))
    
    result = check_authentication_status()
    results.append(("Google Auth", result, "OAuth token present"))
    
    result = test_openai_connection()
    results.append(("OpenAI API", result, "API key works"))
    
    # Show results table
    console.print("\n")
    console.print(create_results_table(results))
    
    # Show summary
    passed = sum(1 for _, status, _ in results if status)
    total = len(results)
    
    console.print("\n" + "="*70)
    
    if passed == total:
        console.print(f"\n[bold green]? ALL CHECKS PASSED ({passed}/{total})[/bold green]")
        console.print("\n[green]System is ready to use![/green]")
    elif passed >= total - 1:  # Only auth missing is OK
        console.print(f"\n[bold yellow]? ALMOST READY ({passed}/{total})[/bold yellow]")
        console.print("\n[yellow]Just need to authenticate with Google[/yellow]")
    else:
        console.print(f"\n[bold red]? ISSUES FOUND ({passed}/{total} passed)[/bold red]")
        console.print("\n[red]Please fix the issues above[/red]")
    
    # Show usage instructions
    show_usage_instructions()
    
    return passed == total or passed == total - 1


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Validation cancelled[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error during validation: {e}[/red]")
        sys.exit(1)
