from typer import Typer
from rich.console import Console
from rich.table import Table
from rrpo_search.utils import download_xml, parse_xml, get_xml_path
import os

from rapidfuzz import process, fuzz


app = Typer(
	help='[blue bold]Инструмент для поиска по РРПО[/blue bold]',
	add_completion=False,
	context_settings=dict(help_option_names=["-h", "--help"])
)
console = Console()


@app.command()
def search(query: str):
	'''[blue bold]Поиск по реестру[/blue bold]'''
	#best_match = process.extractOne(query, vocab, scorer=fuzz.WRatio)
	# query both this and user query
	pass

@app.command()
def refresh():
	'''[blue bold]Обновление сохраненного реестра[/blue bold]'''
	console.print('[blue bold]Обновление реестра...[/blue bold]')
	#download_xml()
	parse_xml()
	console.print('[blue bold]Удаление временного XML...[/blue bold]')
	#os.remove(get_xml_path())
	console.print('[blue green]Реестр обновлен![/blue green]')


if __name__ == "main":
	app()