# Bitrix24 Analytics

Управленческая аналитика по всем воронкам CRM Bitrix24.
Устанавливается как приложение из маркетплейса или работает через webhook.

## Возможности

- **Дашборд по воронкам** — конверсия, pipeline, выручка, тренды MoM
- **Аналитика по менеджерам** — конверсия, динамика выиграно/создано
- **Воронки по стадиям** — drop-off анализ, визуализация
- **Динамика по месяцам** — 12 месяцев с дельтами MoM, по каждой воронке отдельно
- **Анализ старения** — возрастные корзины сделок в работе
- **Зона рисков** — просроченные и замершие сделки
- **Executive Summary** — топы, проблемы, рекомендации

## Два режима работы

### 1. Webhook (быстрый старт)

Не требует установки в маркетплейс. Ограничение: имена менеджеров недоступны (только ID).

```bash
# Запуск локально
pip install -r requirements.txt
python wsgi.py

# Открыть http://localhost:5000/webhook
# Вставить webhook URL вашего Bitrix24
```

### 2. Локальное приложение в Bitrix24 (рекомендуется)

Устанавливается прямо в ваш портал за 2 минуты. Не требует публикации в маркетплейс.

#### Шаг 1: Запустите сервер

```bash
pip install -r requirements.txt
python wsgi.py
# Сервер запущен на http://localhost:5000
```

Для доступа из Bitrix24 нужен публичный HTTPS URL. Варианты:
- **ngrok**: `ngrok http 5000` → получите URL вида `https://xxxx.ngrok.io`
- **Сервер**: деплой через Docker (см. ниже)

#### Шаг 2: Создайте локальное приложение в Bitrix24

1. Откройте ваш Bitrix24 → **Разработчикам** (левое меню внизу) → **Другое** → **Локальное приложение**
2. Заполните:
   - **Название**: `Управленческая аналитика`
   - **Описание**: `Дашборд аналитики по воронкам CRM`
   - **URL вашего обработчика**: `https://ваш-домен.com/install`
   - **URL первоначальной установки**: `https://ваш-домен.com/install`
   - **Права**: отметьте `crm` и `user` (user нужен для имён менеджеров)
3. Нажмите **Сохранить** → скопируйте `client_id` и `client_secret`

#### Шаг 3: Настройте .env

```bash
cp .env.example .env
# Заполните:
# BITRIX24_CLIENT_ID=local.xxxxxxxxxxxx.xxxxxxxx
# BITRIX24_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
# APP_BASE_URL=https://ваш-домен.com
```

#### Шаг 4: Установите приложение

Перейдите в Bitrix24 → **Приложения** → найдите «Управленческая аналитика» → **Установить**.
Приложение появится в левом меню. При открытии — автоматически подключится к CRM и построит дашборд.

### 3. Marketplace (массовое распространение)

Для публикации в маркетплейс Bitrix24:

1. Откройте https://marketplace.bitrix24.com/devops/
2. Создайте приложение:
   - **Тип**: серверное
   - **URL обработчика**: `https://your-domain.com/install`
   - **Права**: `crm`, `user`
3. Скопируйте `CLIENT_ID` и `CLIENT_SECRET`

#### Настройка .env

```bash
cp .env.example .env
# BITRIX24_CLIENT_ID=app.xxxxxxxxx
# BITRIX24_CLIENT_SECRET=xxxxxxxxxxxxxxxx
# APP_BASE_URL=https://your-domain.com
```

#### Запуск через Docker

```bash
docker compose up -d
```

#### Запуск без Docker

```bash
pip install -r requirements.txt
python wsgi.py
```

## Структура проекта

```
app/
  __init__.py       — Flask app factory
  auth.py           — OAuth2 flow (install, refresh tokens)
  bitrix_api.py     — REST API client с автопагинацией
  analytics.py      — Ядро аналитики (чистые вычисления)
  dashboard.py      — HTML-генератор дашборда
  models.py         — Модели БД (Portal, CachedData)
  routes.py         — Flask routes + WebhookClient
wsgi.py             — Entrypoint
```

## API

| Route | Метод | Описание |
|-------|-------|----------|
| `/` | GET | Главная страница |
| `/install` | POST | Установка из маркетплейса |
| `/dashboard?DOMAIN=...` | GET | Дашборд для портала |
| `/webhook?url=...` | GET | Webhook-режим |
| `/uninstall` | POST | Удаление приложения |

## Кеширование

Данные кешируются на 1 час (в БД для marketplace, в памяти для webhook).
При повторном открытии дашборда данные берутся из кеша.

## Лицензия

MIT
