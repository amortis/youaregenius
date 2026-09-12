# youaregenius — персональный аналог Genius

Личное «гении»-пространство: ищем трек на Genius → парсим текст → переводим на русский (DeepL + ручная правка) → добавляем свои аннотации к фрагментам текста → всё хранится под своим аккаунтом.

## Стек

- Python 3.12 + `pip`/`venv` + `requirements.txt`
- Flask 3, Flask-SQLAlchemy, Flask-Migrate (Alembic), Flask-Login, Flask-WTF
- SQLAlchemy: SQLite для разработки / PostgreSQL для прода (переключение конфигом)
- `requests` + `beautifulsoup4` — скрейпинг Genius
- DeepL (free tier) через абстракцию `TranslationProvider` (можно подменить на Яндекс/Libre)
- Bootstrap 5 + HTMX (шаблоны Jinja2)
- `pytest` для тестов

## Поиск на Genius без официального API

Сайт genius.com сам ходит во внутренний JSON-endpoint, работающий без токенов:

```
GET https://genius.com/api/search/multi?per_page=10&q=<query>
```

Возвращает результаты по песням/артистам/альбомам (id, title, artist, cover, url). Затем скрейпим страницу трека через BeautifulSoup: текст из `<div data-lyrics-container="true">`, метаданные из og-тегов. Официальный API не нужен.

## Архитектура

```
youaregenius/
├── app/
│   ├── __init__.py            # create_app(), регистрация blueprint-ов
│   ├── config.py              # DevConfig (SQLite) / ProdConfig (Postgres из env)
│   ├── extensions.py          # db, migrate, login_manager
│   ├── models/
│   │   ├── __init__.py        # db-модели: User, Track, UserTrack, Translation, Annotation
│   ├── blueprints/
│   │   ├── auth/              # регистрация, логин, логаут
│   │   ├── tracks/            # поиск, импорт, «мои треки», страница трека
│   │   ├── annotations/       # CRUD аннотаций (HTMX, без перезагрузки)
│   │   └── translations/      # генерация перевода + ручная правка
│   ├── services/
│   │   ├── genius.py          # search(query) + scrape_track(url) — requests + BS4
│   │   ├── translation.py     # TranslationProvider (abstract) + DeepLProvider
│   │   └── annotations.py     # валидация/нормализация оффсетов
│   ├── templates/             # base.html + папки по блюпринтам (Jinja2)
│   └── static/                # css/js (Bootstrap + HTMX)
├── migrations/                # Alembic через Flask-Migrate
├── tests/                     # pytest
├── requirements.txt
├── run.py
└── .env.example
```

## Модели данных

Треки **общие** (глобальные), чтобы два пользователя, импортирующие один и тот же трек, не плодили дубликаты:

```
User         id, username(UNIQUE), password_hash, created_at

Track        id, genius_id(UNIQUE), title, artist, album,
             cover_url, source_url, lyrics, created_at
             # lyrics — оригинальный текст с Genius (эталонная 'en'-версия)

UserTrack    id, user_id FK→User, track_id FK→Track, created_at
             UNIQUE(user_id, track_id)
             # «добавить трек себе» (N:M)

Translation  id, user_id FK→User, track_id FK→Track, lang,
             content, source("auto"/"manual"), created_at, updated_at
             UNIQUE(user_id, track_id, lang)
             # перевод персональный: у каждого юзера своя версия на язык

Annotation   id, user_id FK→User, track_id FK→Track,
             translation_id FK→Translation (NULL = по оригиналу),
             start_offset, end_offset, content, excerpt, created_at, updated_at
```

Ключевая идея: аннотации привязаны либо к оригиналу (`translation_id IS NULL`, оффсеты относительно `Track.lyrics`), либо к своему переводу (`translation_id`, оффсеты относительно `Translation.content`). `excerpt` — закэшированный вырезанный фрагмент.

## Endpoints

- `/`, `/register`, `/login`, `/logout`
- `/tracks/my` — мои треки
- `/genius/search?q=` — поиск на Genius; `/genius/import/<genius_id>` — импорт в общий каталог
- `/tracks/<id>` — страница трека: текст + аннотации
- `/tracks/<id>/editor` — редактор: выделяешь текст → аннотация
- `/annotations` (HTMX) — создание/правка/удаление аннотаций без перезагрузки
- `/tracks/<id>/translate` — генерация перевода (DeepL) + редактор правки

## Интерактив

В редакторе выделяешь фрагмент текста, JS синхронизирует выделение со скрытым textarea → считывает `selectionStart/End` → HTMX POST → сервер режет `content[start:end]`, сохраняет `excerpt` и аннотацию.

## План работ (milestones)

1. Скелет: factory, config, extensions, модели, миграция, base.html, навигация.
2. Аккаунты: register/login/logout + защита роутов.
3. Genius-сервис + поиск + импорт трека с текстом.
4. Страница трека + редактор аннотаций с оффсетами (HTMX).
5. Перевод: абстракция + DeepL + страница правки перевода.
6. Полировка: README, тесты, `.env.example`, Docker-композ для Postgres-прода.

## Тесты

- Гения-парсер на зафиксированном HTML (без сети).
- Юнит-тесты оффсетов аннотаций.
- CRUD auth и импорт трека на SQLite.