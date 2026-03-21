from typer import Typer
from rich.console import Console
from rrpo_search.utils import download_xml, parse_xml, get_xml_path, get_db_path, get_db_conn, columns_query, print_matches
import os
from rapidfuzz import process, fuzz
import sqlite3


app = Typer(
	help='[blue bold]Инструмент для поиска по РРПО[/blue bold]',
	add_completion=False,
	context_settings=dict(help_option_names=["-h", "--help"])
)
console = Console()


@app.command()
def search(query: str, raw: bool = False):
	'''[blue bold]Поиск по реестру. Используйте [light blue]--raw[/light blue] для прямых SQL-запросов[/blue bold]'''
	if not get_db_path().exists():
		console.print('[bold yellow]Не найдено файла базы данных. Обновление реестра[/bold yellow]')
		refresh()

	cursor = get_db_conn().cursor()

	if raw:
		console.print(f'[blue bold]Поиск в режиме raw\nЗапрос: "{query}"[/blue bold]')
		try:
			cursor.execute(query)
		except sqlite3.Error as error:
			console.print(f'[red bold]Ошибка SQLite3: {error}[/red bold]')
			return

		console.print(f'[green]{cursor.fetchall()}[/green]')
		return

	cursor.execute('SELECT term FROM reestr_vocab')
	vocab = list[str](map(lambda x: x[0], cursor.fetchall()))

	word_matches = list[str]()
	for word in query.split():
		match = process.extractOne(word, vocab, scorer=fuzz.token_sort_ratio)
		if match is not None:
			word_matches.append(match[0])

	matches = list[tuple()]()
	cursor.execute(f'SELECT {columns_query} FROM reestr WHERE reestr MATCH ? LIMIT 50', (' '.join(word_matches),))
	matches.extend(cursor.fetchall())
	if 1 < len(word_matches):
		for i in word_matches:
			cursor.execute(f'SELECT {columns_query} FROM reestr WHERE reestr MATCH ? LIMIT 10', (i,))
			matches.extend(cursor.fetchall())

	added_nums = set[int]()
	final_matches = list[tuple()]()
	for i in matches:
		num = int(i[0]) # type: ignore
		if num not in added_nums:
			added_nums.add(num)
			final_matches.append(i)

	if (len(final_matches)):
		console.print(f'[green bold]Найдено {len(final_matches)} результатов по запросу "{query}"[/green bold]')
		print_matches(final_matches)
	else:
		console.print(f'[red bold]По запросу "{query}" ничего не найдено. Попробуйте добавить слов или перефразировать запрос[/red bold]')


@app.command()
def refresh():
	'''[blue bold]Обновление сохраненного реестра[/blue bold]'''
	console.print('[blue bold]Обновление реестра...[/blue bold]')
	download_xml()
	parse_xml()
	console.print('[blue bold]Удаление временного XML...[/blue bold]')
	os.remove(get_xml_path())
	console.print('[blue green]Реестр обновлен![/blue green]')


if __name__ == "main":
	app()