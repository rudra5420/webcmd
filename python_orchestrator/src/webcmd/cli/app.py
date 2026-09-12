"""WebCMD CLI application.

Commands:
    webcmd do "..."          Execute a natural-language task
    webcmd status            List active executions
    webcmd inspect <id>      Show execution details
    webcmd cancel <id>       Cancel a running execution
    webcmd version           Show version
"""
from __future__ import annotations

import asyncio
import sys
from uuid import UUID

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from webcmd import __version__
from webcmd.config import WebCMDConfig, get_config
from webcmd.core.orchestrator import Orchestrator
from webcmd.storage.database import DatabaseManager
from webcmd.workers.mock import MockWorker
from webcmd.workers.api.http_worker import HttpWorker
from webcmd.workers.browser.playwright_worker import PlaywrightWorker
from webcmd.workers.browser.browseruse_worker import BrowserUseWorker
from webcmd.workers.filesystem.local_worker import FilesystemWorker
from webcmd.workers.shell.shell_worker import ShellWorker
from webcmd.workers.registry import WorkerRegistry

from webcmd.state.enums import ExecutionStatus

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

app = typer.Typer(
    name="webcmd",
    help="Turn natural-language intent into verified, reusable workflows.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


async def _get_orchestrator(config: WebCMDConfig | None = None) -> tuple[Orchestrator, DatabaseManager]:
    """Create and initialize the orchestrator with all registered workers."""
    cfg = config or get_config()
    cfg.ensure_dirs()
    
    db = DatabaseManager(cfg.get_db_path())
    await db.initialize()
    
    registry = WorkerRegistry()
    registry.register(MockWorker)
    registry.register(HttpWorker)
    registry.register(PlaywrightWorker)
    registry.register(BrowserUseWorker)
    registry.register(FilesystemWorker)
    registry.register(ShellWorker)
    
    orchestrator = Orchestrator(cfg, db, registry)
    return orchestrator, db


@app.command()
def do(
    task: str = typer.Argument(..., help="Natural language task description"),
    auto_approve: bool = typer.Option(
        False,
        "--auto-approve",
        "--auto-confirm",
        help="Automatically confirm execution without interactive prompt",
    ),
) -> None:
    """Execute a natural-language task.
    
    Example:
        webcmd do "Go to example.com and take a screenshot"
        webcmd do "Check server status" --auto-approve
    """
    async def _run():
        orchestrator, db = await _get_orchestrator()
        try:
            console.print(Panel(
                f"[bold blue]Intent:[/] {task}",
                title="WebCMD",
                border_style="blue",
            ))
            
            with console.status("[bold green]Executing..."):
                execution = await orchestrator.execute_task(task, auto_confirm=auto_approve)
            
            # Check if awaiting human verification
            if execution.status == ExecutionStatus.AWAITING_HUMAN_VERIFICATION:
                verification_panel = (
                    f"[bold]FINAL VERIFICATION REQUIRED[/]\n\n"
                    f"[bold cyan]Task:[/] {task}\n\n"
                    f"[bold cyan]WebCMD Result:[/] {execution.result}\n\n"
                    f"[bold green]Automated Verification:[/] Passed\n\n"
                    f"[bold]Options:[/] [1] Confirm execution  [2] Reject execution"
                )
                console.print(Panel(verification_panel, title="Human Verification Gate", border_style="yellow"))
                
                if sys.stdin.isatty():
                    choice = console.input("[bold yellow]Enter choice [1/2] (or c/r): [/]").strip().lower()
                    if choice in ("1", "c", "confirm", "y", "yes"):
                        execution = await orchestrator.confirm_execution(
                            execution.execution_id, verified_by="operator"
                        )
                        console.print(Panel(
                            f"[bold green][OK] Completed (Human Verified)[/]\n"
                            f"Execution ID: {execution.execution_id}\n"
                            f"Result: {execution.result}",
                            title="Result",
                            border_style="green",
                        ))
                    else:
                        reason = console.input("[bold red]Enter rejection reason (optional): [/]").strip()
                        execution = await orchestrator.reject_execution(
                            execution.execution_id, reason=reason, verified_by="operator"
                        )
                        console.print(Panel(
                            f"[bold yellow][REJECTED] Escalated to Recovery / Review[/]\n"
                            f"Execution ID: {execution.execution_id}\n"
                            f"Failure: {execution.failure_code}",
                            title="Result",
                            border_style="yellow",
                        ))
                else:
                    console.print(Panel(
                        f"[bold yellow]Execution paused awaiting human verification.[/]\n"
                        f"Execution ID: {execution.execution_id}\n"
                        f"Run 'webcmd approve {execution.execution_id}' or 'webcmd reject {execution.execution_id}'",
                        title="Action Required",
                        border_style="yellow",
                    ))
            elif execution.status == ExecutionStatus.COMPLETED or execution.status == "completed":
                console.print(Panel(
                    f"[bold green][OK] Completed[/]\n"
                    f"Execution ID: {execution.execution_id}\n"
                    f"Result: {execution.result}",
                    title="Result",
                    border_style="green",
                ))
            else:
                console.print(Panel(
                    f"[bold red][FAIL] {str(execution.status).upper()}[/]\n"
                    f"Execution ID: {execution.execution_id}\n"
                    f"Failure: {execution.failure_code}",
                    title="Result",
                    border_style="red",
                ))
        finally:
            await db.close()
    
    asyncio.run(_run())


@app.command()
def status() -> None:
    """List all executions and their current status."""
    async def _run():
        orchestrator, db = await _get_orchestrator()
        try:
            executions = await orchestrator.list_executions()
            
            if not executions:
                console.print("[dim]No executions found.[/dim]")
                return
            
            table = Table(
                title="WebCMD Executions",
                box=box.ROUNDED,
                show_lines=True,
            )
            table.add_column("ID", style="cyan", max_width=12)
            table.add_column("Status", style="bold")
            table.add_column("Started", style="dim")
            table.add_column("Finished", style="dim")
            
            for ex in executions:
                status_style = {
                    "completed": "[green][OK] completed[/]",
                    "failed": "[red][FAIL] failed[/]",
                    "running": "[yellow][RUN] running[/]",
                    "cancelled": "[dim][CANCEL] cancelled[/]",
                    "pending": "[blue][PENDING] pending[/]",
                    "awaiting_human_verification": "[bold magenta][WAIT] awaiting human verification[/]",
                    "recovering": "[bold yellow][RECOVER] recovering[/]",
                }.get(str(ex.status), str(ex.status))
                
                table.add_row(
                    str(ex.execution_id)[:12] + "...",
                    status_style,
                    str(ex.started_at)[:19] if ex.started_at else "-",
                    str(ex.finished_at)[:19] if ex.finished_at else "-",
                )
            
            console.print(table)
        finally:
            await db.close()
    
    asyncio.run(_run())


@app.command()
def inspect(
    execution_id: str = typer.Argument(..., help="Execution ID to inspect"),
) -> None:
    """Show detailed information about an execution."""
    async def _run():
        orchestrator, db = await _get_orchestrator()
        try:
            try:
                eid = UUID(execution_id)
            except ValueError:
                console.print(f"[red]Invalid execution ID: {execution_id}[/]")
                return
            
            execution = await orchestrator.get_execution(eid)
            if not execution:
                console.print(f"[red]Execution not found: {execution_id}[/]")
                return
            
            # Get events
            events = await orchestrator.event_store.get_events(eid)
            
            # Main panel
            info = (
                f"[bold]Execution ID:[/] {execution.execution_id}\n"
                f"[bold]Task ID:[/] {execution.task_id}\n"
                f"[bold]Status:[/] {execution.status}\n"
                f"[bold]Started:[/] {execution.started_at or '-'}\n"
                f"[bold]Finished:[/] {execution.finished_at or '-'}\n"
            )
            if execution.result:
                info += f"[bold]Result:[/] {execution.result}\n"
            if execution.failure_code:
                info += f"[bold red]Failure:[/] {execution.failure_code}\n"
            if execution.human_verification:
                hv = execution.human_verification
                hv_status = hv.status.value if hasattr(hv.status, "value") else str(hv.status)
                info += (
                    f"\n[bold magenta]Human Verification:[/]\n"
                    f"  Status: {hv_status.upper()}\n"
                    f"  Required: {hv.required}\n"
                    f"  Requested: {str(hv.requested_at)[:19] if hv.requested_at else '-'}\n"
                    f"  Completed: {str(hv.completed_at)[:19] if hv.completed_at else '-'}\n"
                    f"  Verified By: {hv.verified_by or '-'}\n"
                )
                if hv.reason:
                    info += f"  Reason: {hv.reason}\n"
            
            console.print(Panel(info, title="Execution Details", border_style="cyan"))
            
            # Events table
            if events:
                event_table = Table(
                    title="Event Timeline",
                    box=box.SIMPLE,
                )
                event_table.add_column("#", style="dim")
                event_table.add_column("Event", style="cyan")
                event_table.add_column("Time", style="dim")
                event_table.add_column("Details", max_width=50)
                
                for ev in events:
                    event_table.add_row(
                        str(ev.sequence_number),
                        ev.event_type,
                        str(ev.timestamp)[:19],
                        str(ev.payload)[:50],
                    )
                
                console.print(event_table)
        finally:
            await db.close()
    
    asyncio.run(_run())


@app.command()
def approve(
    execution_id: str = typer.Argument(..., help="Execution ID to approve and complete"),
) -> None:
    """Confirm and complete an execution awaiting final human verification.
    
    Example:
        webcmd approve 12345678-1234-5678-1234-567812345678
    """
    async def _run():
        orchestrator, db = await _get_orchestrator()
        try:
            try:
                eid = UUID(execution_id)
            except ValueError:
                console.print(f"[red]Invalid execution ID: {execution_id}[/]")
                return
            
            execution = await orchestrator.confirm_execution(eid, verified_by="operator")
            console.print(Panel(
                f"[bold green][OK] Execution Confirmed & Completed[/]\n"
                f"Execution ID: {execution.execution_id}\n"
                f"Status: {execution.status}\n"
                f"Result: {execution.result}",
                title="Human Verification",
                border_style="green",
            ))
        except ValueError as e:
            console.print(f"[red]Error: {e}[/]")
        finally:
            await db.close()
    
    asyncio.run(_run())


@app.command()
def confirm(
    execution_id: str = typer.Argument(..., help="Execution ID to confirm (alias for approve)"),
) -> None:
    """Alias for 'approve'."""
    approve(execution_id)


@app.command()
def reject(
    execution_id: str = typer.Argument(..., help="Execution ID to reject"),
    reason: str = typer.Option("", "--reason", "-r", help="Reason for rejection"),
) -> None:
    """Reject an execution awaiting human verification and escalate to recovery / review.
    
    Example:
        webcmd reject 12345678-1234-5678-1234-567812345678 --reason "Incorrect output directory"
    """
    async def _run():
        orchestrator, db = await _get_orchestrator()
        try:
            try:
                eid = UUID(execution_id)
            except ValueError:
                console.print(f"[red]Invalid execution ID: {execution_id}[/]")
                return
            
            execution = await orchestrator.reject_execution(
                eid, reason=reason, verified_by="operator"
            )
            console.print(Panel(
                f"[bold yellow][REJECTED] Execution Escalated to Recovery[/]\n"
                f"Execution ID: {execution.execution_id}\n"
                f"Status: {execution.status}\n"
                f"Failure Code: {execution.failure_code}",
                title="Human Verification",
                border_style="yellow",
            ))
        except ValueError as e:
            console.print(f"[red]Error: {e}[/]")
        finally:
            await db.close()
    
    asyncio.run(_run())


@app.command()
def cancel(
    execution_id: str = typer.Argument(..., help="Execution ID to cancel"),
) -> None:
    """Cancel a running execution."""
    async def _run():
        orchestrator, db = await _get_orchestrator()
        try:
            try:
                eid = UUID(execution_id)
            except ValueError:
                console.print(f"[red]Invalid execution ID: {execution_id}[/]")
                return
            
            execution = await orchestrator.cancel_execution(eid)
            if execution:
                console.print(f"[yellow]Execution {execution_id[:12]}... cancelled.[/]")
            else:
                console.print(f"[red]Execution not found: {execution_id}[/]")
        finally:
            await db.close()
    
    asyncio.run(_run())


@app.command()
def resume(
    execution_id: str = typer.Argument(..., help="Execution ID to resume from checkpoint"),
    auto_approve: bool = typer.Option(False, "--auto-approve", "--auto-confirm", help="Auto-confirm after resume"),
) -> None:
    """Resume an execution from its latest valid checkpoint.
    
    Example:
        webcmd resume 12345678-1234-5678-1234-567812345678
    """
    async def _run():
        orchestrator, db = await _get_orchestrator()
        try:
            try:
                eid = UUID(execution_id)
            except ValueError:
                console.print(f"[red]Invalid execution ID: {execution_id}[/]")
                return
            
            execution = await orchestrator.resume_execution(eid, auto_confirm=auto_approve)
            console.print(Panel(
                f"[bold green]Execution Resumed Successfully[/]\n"
                f"Execution ID: {execution.execution_id}\n"
                f"Status: {execution.status}\n"
                f"Result: {execution.result}",
                title="Checkpoint Resume",
                border_style="cyan",
            ))
        except ValueError as e:
            console.print(f"[red]Error: {e}[/]")
        finally:
            await db.close()
    
    asyncio.run(_run())


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host interface to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
) -> None:
    """Launch the WebCMD local web control and visualization dashboard.
    
    Example:
        webcmd web
        webcmd web --port 8080
    """
    import uvicorn
    from webcmd.web.server import create_app
    
    console.print(Panel(
        f"[bold green]WebCMD Web Control Dashboard[/]\n\n"
        f"Server URL: [bold cyan]http://{host}:{port}[/]\n"
        f"API Docs:   [dim]http://{host}:{port}/docs[/]\n"
        f"Real-time:  [magenta]WebSocket & REST[/]\n\n"
        f"[dim]Press Ctrl+C to stop the server.[/dim]",
        title="WebCMD Server",
        border_style="cyan",
    ))
    
    app_instance = create_app()
    uvicorn.run(app_instance, host=host, port=port, log_level="info")


@app.command()
def version() -> None:
    """Show WebCMD version."""
    console.print(f"WebCMD v{__version__}")


if __name__ == "__main__":
    app()

