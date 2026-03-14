from typer import Typer
from rich.console import Console
from rich.table import Table


app = Typer(
	help='[blue bold]Инструмент для поиска по ЕРРП[/blue bold]',
	add_completion=False,
	context_settings=dict(help_option_names=["-h", "--help"])
)
console = Console()


@app.command()
def search():
	pass


@app.command()
def refresh():
	pass


if __name__ == "main":
	app()