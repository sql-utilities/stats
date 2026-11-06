# dbstat

Dbstat подключается к SQL-базе и печатает статистику по таблицам и колонкам: количество строк, пропуски, уникальные значения, min/max, среднее, стандартное отклонение и топ значений.

**Чем dbstat не является.** Это только чтение. Он не чистит данные, не мигрирует и ничего не меняет: сразу после подключения выставляется `SET default_transaction_read_only = on`, а в коде нет ни одного INSERT/UPDATE/DELETE/DDL. Агрегаты считаются на стороне БД, в Python строки не вытягиваются.

```
--url ──► dialect (postgres) ──► агрегаты в БД ──► TableStats ──► render (table | json | md)
```

---

## Установка

```
pip install -e ".[postgres]"
```

Требуется Python `3.10+`. Драйвер `psycopg[binary]>=3.1` ставится как extra `postgres` и для импорта пакета не нужен. Без него утилита сообщит: `pip install 'dbstat[postgres]'`.

## Тестовая база

```
export PG_URL="postgresql://postgres:postgres@localhost:5432/postgres"
bash testdata/run_checks.sh
```

Скрипт (нужен `psql`) создаёт схему `dbstat_demo` (идемпотентно), прогоняет `dbstat` и сверяет отчёт с `testdata/expected_users.txt`. Каждая строка этого файла — регулярное выражение, которое должно совпасть со строкой отчёта. Данные в сиде задаются формулами без `random()`, поэтому числа точные. Время `created_at` проверяется с допуском на часовой пояс сервера.

Сид даёт 1240 пользователей (40 без email, 259 без age, статусы active 868 / blocked 248 / deleted 124) и 8300 заказов.

## Примеры

```
dbstat --url "$PG_URL" --schema dbstat_demo
dbstat --url "$PG_URL" --schema dbstat_demo --table users --columns age,status
dbstat --url "$PG_URL" --schema dbstat_demo --table orders --format json --limit 1000
```

Вывод для `--table users`:

```
schema: dbstat_demo

table: users  (row_count=1240, columns=5)
  id          integer      non_null=1240  null=0            distinct=1240  min=1                     max=1240                  mean=620.5  std=358.1
  email       text         non_null=1200  null=40 (3.2%)    distinct=1143  top: user10@example.com(2), user11@example.com(2), ...
  age         integer      non_null=981   null=259 (20.9%)  distinct=75    min=18                    max=92                    mean=55.29  std=21.63
  created_at  timestamptz  non_null=1240  null=0            distinct=1240  min=2023-01-03 05:00:00…  max=2024-12-27 20:00:00…
  status      text         non_null=1240  null=0            distinct=3     top: active(868), blocked(248), deleted(124)
```

## Флаги

| Флаг | Описание |
|------|----------|
| `--url` | DSN (обязательный) |
| `--db` | СУБД из реестра диалектов, по умолчанию `postgres` |
| `--schema` | схема, по умолчанию `public` |
| `--table` | таблицы через запятую, по умолчанию все базовые таблицы схемы (представления не входят) |
| `--columns` | колонки через запятую, по умолчанию все |
| `--format` | `table` (по умолчанию), `json`, `md` |
| `--top` | сколько топ-значений показывать, по умолчанию 5, `0` отключает |
| `--limit` | считать статистику по первым N строкам таблицы |

Код возврата: `0` при успехе, `1` если нет таблиц или колонок для отчёта либо запрос не удался.

## Сэмплирование (`--limit`)

`--limit N` включает сэмплирование: если в таблице больше N строк, статистика считается по `SELECT * FROM t LIMIT N`, а в заголовке таблицы появляется пометка `[sampled: limit=N]` (в json это `"sampled": true` и `"sample_limit": N`). **Все числа колонок (non_null, null, distinct, min, max, mean, std, топ) относятся к сэмплу, а не к таблице целиком.** Только `row_count` в заголовке всегда настоящий, его считает честный `COUNT(*)`. Сэмпл берётся без `ORDER BY`, то есть это «первые попавшиеся N строк», а не случайная выборка. Если строк не больше N, сэмплирования нет и пометки нет.

Без `--limit` для таблиц больше 1 000 000 строк в stderr выводится предупреждение, но работа продолжается.

## Решения по формату

- `null=0` печатается всегда, а `null=<n> (<pct>%)` с процентом только если пропуски есть.
- `mean` и `std` только у числовых колонок. `std=-`, если значений меньше двух (`mean=-` для колонки без значений).
- min/max и топ-значения в `table` и `md` обрезаются до 20 символов (последний символ `…`), в `json` выводятся полностью.
- Топ-значения печатаются через запятую, значение в кавычках, если содержит пробел или запятую.
- Топ считается только для текстовых колонок (не числовых и не дата/время) и только если есть повторы, иначе все частоты равны 1. У такой колонки вместо min/max показывается топ.
- Типы без сравнения или min/max (`json`, `point`, `boolean` и т.п.) считаются повторным запросом через `::text`.
- В отчёте `timestamp with time zone` печатается как `timestamptz`, `character varying` как `varchar`. Время печатается в часовом поясе сессии.
- Колонки внутри таблицы идут в порядке объявления, `--columns` лишь фильтрует их. Несуществующие таблицы и колонки пропускаются с сообщением в stderr.

## Структура проекта

```
dbstat/
├── pyproject.toml
├── README.md
├── dbstat/
│   ├── __init__.py          ← __version__
│   ├── models.py            ← ColumnMeta, ColumnAgg, ColumnStats, TableStats
│   ├── registry.py          ← register(), get_dialect(), available_dialects()
│   ├── stats.py             ← сборка TableStats из диалекта
│   ├── render.py            ← render_table, render_json, render_md
│   ├── cli.py               ← argparse, main()
│   └── dialects/
│       ├── __init__.py      ← импорты диалектов для регистрации
│       ├── base.py          ← abc Dialect
│       └── postgres.py      ← PostgresDialect
└── testdata/
    ├── seed_postgres.sql
    ├── run_checks.sh
    └── expected_users.txt
```

## Как добавить диалект

1. Создать файл `dbstat/dialects/<name>.py` и класс-наследник `Dialect` с декоратором `@register("<name>")`.
2. Реализовать 4 метода:
   - `list_tables(schema) -> list[str]`
   - `table_row_count(table, schema) -> int`
   - `column_metadata(table, schema) -> list[ColumnMeta]`
   - `column_aggregates(table, column, schema, limit, top) -> ColumnAgg`, где `column` это `ColumnMeta`, а `limit` уже учтён (`None` значит без сэмпла).
3. Добавить одну строку импорта в `dbstat/dialects/__init__.py`: `from dbstat.dialects import <name>`.
4. Добавить extra с драйвером в `pyproject.toml` (`[project.optional-dependencies]`).

Импорт драйвера делайте необязательным (как в `postgres.py`): пакет должен импортироваться без него, а ошибка с подсказкой по установке появляется только при подключении. Идентификаторы экранируйте средствами драйвера, значения передавайте параметрами, а не конкатенацией.
# stats
