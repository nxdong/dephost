import asyncio
import sys
from typing import Dict, List

import httpx
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()


async def check_endpoint(
    client: httpx.AsyncClient, url: str, name: str
) -> Dict[str, bool]:
    try:
        response = await client.get(url)
        return {
            "name": name,
            "status": response.status_code == 200,
            "code": response.status_code,
        }
    except Exception as e:
        return {"name": name, "status": False, "error": str(e)}


async def run_checks(base_url: str) -> List[Dict[str, bool]]:
    endpoints = [
        ("/", "Root Endpoint"),
        ("/health", "Health Check"),
        ("/pypi/simple", "PyPI Simple Index"),
        ("/pypi/requests/info", "PyPI Package Info"),
    ]

    async with httpx.AsyncClient() as client:
        tasks = [
            check_endpoint(client, f"{base_url}{path}", name)
            for path, name in endpoints
        ]
        return await asyncio.gather(*tasks)


@app.command()
def check(
    host: str = typer.Option("127.0.0.1", help="Service host"),
    port: int = typer.Option(8000, help="Service port"),
):
    """检查 DepHost 服务状态"""
    base_url = f"http://{host}:{port}"

    with console.status("Checking service..."):
        results = asyncio.run(run_checks(base_url))

    # 创建结果表格
    table = Table(title="Service Status")
    table.add_column("Endpoint", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="yellow")

    all_success = True
    for result in results:
        status = "✓" if result["status"] else "✗"
        details = (
            str(result.get("code", ""))
            if result["status"]
            else result.get("error", "Failed")
        )
        table.add_row(result["name"], status, details)
        if not result["status"]:
            all_success = False

    console.print(table)
    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    app()
