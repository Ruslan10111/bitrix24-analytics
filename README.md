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

### 2. Marketplace (полная версия)

OAuth2 приложение с полным доступом к CRM + User API.

#### Регистрация в маркетплейсе

1. Откройте https://marketplace.bitrix24.com/devops/
2. Создайте приложение:
   - **Тип**: серверное
   - **URL обработчика**: `https://your-domain.com/install`
   - **Права**: `crm`, `user`
3. Скопируйте `CLIENT_ID` и `CLIENT_SECRET`

#### Настройка

```bash
cp .env.example .env
# Заполните .env:
# BITRIX24_CLIENT_ID=...
# BITRIX24_CLIENT_SECRET=...
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
