from platformdirs import user_data_dir
from pathlib import Path
from lxml import etree
import httpx
import sqlite3
import os
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn, TextColumn, SpinnerColumn, TimeRemainingColumn
from rich.console import Console
from rich.table import Table


columns = """
	reg_num UNINDEXED,
	name,
	prev_alias,
	module,
	owner,
	owner_short,
	description_link UNINDEXED,
	cost_link UNINDEXED,
	gos_reg_date UNINDEXED,
	gos_reg_num UNINDEXED,
	incl_date UNINDEXED,
	incl_num UNINDEXED,
	excluded UNINDEXED,
	excl_date UNINDEXED,
	excl_num UNINDEXED,
	excl_type UNINDEXED
"""
columns_names = [
	'Номер записи',
	'Название',
	'Пред. название',
	'Модуль',
	'Владелец',
	'Владелец (сокращ.)',
	'Описание (URL)',
	'Цена (URL)',
	'Дата гос. регистр.',
	'Номер гос. регистр.',
	'Дата включения',
	'Номер включения',
	'Исключено',
	'Дата искл.',
	'Номер искл.',
	'Тип искл.'
]
columns_query = columns.replace(' UNINDEXED', '')


def get_data_path():
	data_dir = Path(user_data_dir('rrpo-search'))
	data_dir.mkdir(parents=True, exist_ok=True)

	return data_dir


def get_db_path():
	return get_data_path()/'reestr.db'


def get_db_conn():
	conn = sqlite3.connect(get_db_path())
	return conn


def reinit_db():
	if (get_db_path().exists()):
		os.remove(get_db_path())

	conn = get_db_conn()
	conn.execute("PRAGMA journal_mode = MEMORY")
	conn.execute("PRAGMA synchronous = OFF")
	conn.execute(f"""
		CREATE VIRTUAL TABLE IF NOT EXISTS reestr_raw
		USING fts5(
			{columns},
			tokenize='unicode61'
		)
	""")
	conn.execute(f"""
		CREATE VIRTUAL TABLE IF NOT EXISTS reestr
		USING fts5(
			{columns},
			tokenize='trigram'
		)
	""")
	conn.execute("""
		CREATE VIRTUAL TABLE IF NOT EXISTS reestr_vocab
		USING fts5vocab(reestr_raw, 'row')
	""")

	return conn


def get_xml_path():
	return get_data_path()/'reestr-temp.xml'


def parse_xml():
	Console().print('[blue bold]Пересоздание базы данных...[/blue bold]')
	conn = reinit_db()
	cursor = conn.cursor()
	xml_size = os.path.getsize(get_xml_path())

	with Progress(
		SpinnerColumn(),
		TextColumn("[bold blue]Перевод в базу данных..."),
		BarColumn(bar_width=None),
		"[progress.percentage]{task.percentage:>3.1f}%",
		TimeRemainingColumn(),
	)  as progress:
		with open(get_xml_path(), 'rb') as f:
			context = etree.iterparse(f, events=('end',), tag='item')
			task = progress.add_task('index-xml', total=xml_size)

			for num, (_, i) in enumerate(context):
				reg_num = i.findtext('registrationNumber')
				name = i.findtext('name')
				prev_alias = i.findtext('previousAlternativeName')
				module = i.find('module')
				if module is not None:
					module = module.findtext('name')
				owner_short = owner = i.find('owner')
				if owner is not None and owner_short is not None:
					owner = owner.findtext('name')
					owner_short = owner_short.findtext('shortName')
				description_link = i.findtext('descriptionLink')
				cost_link = i.findtext('costLink')
				gos_reg_date = i.findtext('gosRegistrationDate')
				gos_reg_num = i.findtext('gosRegistrationNumber')
				incl_date = i.findtext('inclusionDate')
				incl_num = i.findtext('inclusionNumber')
				excluded = i.findtext('excluded')
				excl_date = i.findtext('exclusionDate')
				excl_num = i.findtext('exclusionNumber')
				excl_type = i.findtext('exclusionType')

				cursor.execute(
					f"""
						INSERT INTO reestr (
							{columns_query}
						) VALUES (
							?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
						)
					""",
					(reg_num, name, prev_alias, module, owner, owner_short, description_link, cost_link, gos_reg_date, gos_reg_num, incl_date, incl_num, excluded, excl_date, excl_num, excl_type)
				)
				cursor.execute(
					f"""
						INSERT INTO reestr_raw (
							{columns_query}
						) VALUES (
							?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
						)
					""",
					(reg_num, name, prev_alias, module, owner, owner_short, description_link, cost_link, gos_reg_date, gos_reg_num, incl_date, incl_num, excluded, excl_date, excl_num, excl_type)
				)

				if num % 500 == 0:
					progress.update(task, completed=f.tell())

				i.clear()
				parent = i.getparent()
				if parent is not None:
					while i.getprevious() is not None:
						del parent[0]

			conn.commit()

		progress.update(task, completed=xml_size)


def download_xml():
	with httpx.stream('GET', 'https://reestr.digital.gov.ru/reestr/?export=registry', follow_redirects=True) as stream:
		total = int(stream.headers.get('Content-Length', 0))

		with Progress(
			TextColumn("[bold blue]{task.description}[/bold blue]"),
			BarColumn(bar_width=None),
			"[progress.percentage]{task.percentage:>3.1f}%",
			DownloadColumn(),
			TransferSpeedColumn(),
		) as progress:
			task = progress.add_task('Загрузка XML...', total=total)

			with open(get_xml_path(), 'wb') as f:
				for i in stream.iter_bytes():
					f.write(i)

					progress.update(task, advance=len(i))


def print_matches(matches: list[tuple[()]]):
	table = Table(show_lines=True, highlight=True)

	for i in columns_names:
		table.add_column(i, overflow='fold')

	for i in matches:
		row_data = list[str]()
		for j in range(len(columns_names)):
			row_data.append(i[j])
			if row_data[-1] == '' or row_data[-1] is None: # pyright: ignore[reportUnnecessaryComparison]
				row_data[-1] = '-'
			row_data[-1] = row_data[-1].replace('&quot;', '"')

			if j == 12 and row_data[-1] != 'Нет':
				row_data[-1] = f'[bold red]{row_data[-1]}[/bold red]'

		table.add_row(
			row_data[0], row_data[1], row_data[2], row_data[3], row_data[4], row_data[5], row_data[6], row_data[7], row_data[8], row_data[9], row_data[10], row_data[11], row_data[12], row_data[13], row_data[14], row_data[15]
		)

	Console().print(table)