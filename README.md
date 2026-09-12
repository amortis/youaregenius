# youaregenius

Персональный аналог [Genius](https://genius.com): ищите трек на Genius,
парсите текст, переводите на русский (DeepL + ручная правка) и добавляйте
собственные аннотации к фрагментам текста. Всё хранится под вашим аккаунтом.

## Возможности

- Поиск треков на Genius **без официального API** — через внутренний
  JSON-endpoint `genius.com/api/search/multi` и скрейпинг страниц
  (`requests` + BeautifulSoup).
- Импорт трека с полным текстом: сохраняется **структура** (секции и строки
  с Genius), а не плоский текст.
- Аннотации: выделяете фрагмент текста в редакторе → сохраняется с
  оффсетами `[start:end]` и «вырезанным» фрагментом (`excerpt`).
- Просмотр текста в трёх режимах: **Оригинал** (с подсветкой аннотаций),
  **Русский**, **Два языка** (английская строка / под ней русская).
- Перевод построчно через DeepL (free tier) с сохранением структуры Genius
  и последующей ручной правкой.
- Треки **общие** (глобальный каталог, дедуп по `genius_id`), аннотации и
  переводы — **персональные**.
- Аккаунты: username + пароль (без email).

## Стек

| Слой       | Технологии                                                            |
|------------|-----------------------------------------------------------------------|
| Backend    | Python 3.12, Flask 3 (app factory + blueprints), Flask-WTF, Flask-Login |
| Данные     | Flask-SQLAlchemy (SQLite dev / PostgreSQL prod), Flask-Migrate (Alembic) |
| Парсинг    | `requests` + `beautifulsoup4`                                         |
| Перевод    | DeepL API через абстракцию `TranslationProvider` (плагинный)          |
| Frontend   | Bootstrap 5 (Jinja2), HTMX — интерактив без перезагрузки              |
| Тесты      | pytest (21 тест)                                                      |
| Продакшен  | gunicorn, PostgreSQL                                                  |

## Архитектура

```
youaregenius/
├── app/
│   ├── __init__.py            # create_app(): конфиг, расширения, blueprints
│   ├── config.py              # Dev (SQLite) / Test / Prod (Postgres из env)
│   ├── extensions.py          # db, migrate, login_manager, csrf
│   ├── models/                # User, Track, UserTrack, Translation, Annotation
│   ├── blueprints/
│   │   ├── auth/              # регистрация, логин, логаут
│   │   ├── tracks/            # «мои треки», поиск, импорт, страница трека, редактор
│   │   ├── annotations/       # HTMX-CRUD аннотаций
│   │   └── translations/      # генерация перевода + ручная правка
│   ├── services/              # бизнес-логика, отделённая от роутов
│   │   ├── genius.py          # search() + scrape_track() (requests + BS4)
│   │   ├── translation.py     # TranslationProvider / DeepLProvider
│   │   ├── annotations.py     # валидация оффсетов, highlight()
│   │   └── structures.py      # JSON-структура <-> плоский текст
│   ├── templates/             # Jinja2 (base + папки по blueprint-ам)
│   └── static/                # css/js
├── migrations/                # Alembic (Flask-Migrate)
├── tests/                     # pytest
├── docs/
│   ├── PROJECT_PLAN.md        # план, схема БД, milestones
│   └── WORKLOG.md             # журнал разработки
├── run.py                     # dev-сервер
├── requirements.txt
├── pytest.ini
└── .env.example               # шаблон переменных окружения
```

### Поток данных

```
Запрос --> Blueprint (routes) --> Service (gений/перевод/аннотации)
   --> Models (SQLAlchemy) --> SQLite/PostgreSQL
                        ^
              Jinja2 + Bootstrap + HTMX (частичные шаблоны)
```

## Модели данных

```
User         id, username(UNIQUE), password_hash, created_at

Track        id, genius_id(UNIQUE), title, artist, album, cover_url,
             source_url, lyrics, structure(JSON), created_at
             # lyrics — плоский текст (эталон для оффсетов);
             # structure — секции [{heading, lines}] с Genius

UserTrack    user_id FK, track_id FK, created_at
             UNIQUE(user_id, track_id)     # «добавить трек себе» (N:M)

Translation  user_id FK, track_id FK, lang, content, structure(JSON),
             source("auto"|"manual"), created_at, updated_at
             UNIQUE(user_id, track_id, lang)

Annotation   user_id FK, track_id FK, translation_id FK(NULL), 
             start_offset, end_offset, content, excerpt, created_at, updated_at
```

Ключевые идеи:

- **Трек глобальный** — уникален по `genius_id`. Два пользователя,
  импортировавшие один трек, не плодят дубликаты; у каждого свой `UserTrack`.
- **Аннотации привязаны к конкретному тексту**: `translation_id IS NULL` →
  оффсеты по `Track.lyrics` (оригинал); иначе — по содержимому своего
  перевода. Оффсеты всегда валидны, `excerpt` кэширует вырезанный фрагмент.
- **Структура сохраняется**, поэтому возможен двухъязычный просмотр
  «строка под строкой», а перевод строится построчно и не теряет разбивку.

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # задайте SECRET_KEY и (опционально) DEEPL_API_KEY

flask --app run db upgrade  # применить миграции (создаст youaregenius_dev.db)
flask --app run             # http://127.0.0.1:5000
```

### Перевод через DeepL

В `.env` задайте `DEEPL_API_KEY` (free tier: 500k символов/мес) —
появится кнопка «Сгенерировать перевод». Без ключа перевод отключён.

## Тесты

```bash
python -m pytest -q
```

## Продакшен

- PostgreSQL: `DATABASE_URI=postgresql+psycopg2://...` (переключение конфигом,
  `pip install psycopg2-binary`).
- `gunicorn -w 4 -b 0.0.0.0:8000 'app:create_app("prod")'`
- Обязательно задайте `SECRET_KEY` и `DATABASE_URI` в окружении.