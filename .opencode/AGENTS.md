# La Vida Loca — User Profile

## Basic Info
- **Name:** Никита (Nikita)
- **Nickname:** La Vida Loca
- **Occupation:** Железная дорога (railway worker)
- **Language:** Russian (native)

## Personality & Style
- **Communication:** Доброжелательный, с иронией. Избегает агрессии, оскорблений и токсичности
- **Content vibe:** Уважительное комьюнити, где всем весело и комфортно
- **Values:** Честность, адекватность, взаимное уважение

## Interests
- **Gaming:** Сюжетные игры, ККИ (коллекционные карточные игры). Проходит игры от Sony
- **Recent playthrough:** Resident Evil Requiem
- **Anime:** Любит аниме
- **Collecting:** Коллекционирует фигурки
- **Streaming:** Стримит на Twitch @NektarinGaming то, во что играет

## Streaming (current state)
- Формат: Полные записи (без нарезок/монтажа)
- Цель: Собрать адекватное комьюнити, где все уважают друг друга
- Планируется: Нарезка клипов из хайлайтов → TikTok/Shorts

## Telegram Bot (@NektarinGaming)
- **Bot purpose:** Ироничный постинг игровых новостей
- **Schedule:** Каждые 2 часа (через Task Scheduler, больше не включает VPN)
- **Sources:** Igromania, GoHa (3 категории), PlayGround, StopGame, Kanobu, VGTimes, Shazoo
- **Stack:** Python, Telegram Bot API, Steam API, Twitch GQL API, Wikipedia API, DuckDuckGo Images
- **Image lookup (5 уровней):** RSS-превью → Steam → RAWG → SGDB → Wikipedia → DuckDuckGo
- **Features:**
  - Эмодзи-динамика (контекстные эмодзи под тему новости)
  - Категории: продажи, перенос, сиквел, консоль, драма, слух 🔮, анонс 🎉
  - Рекомендации от Никиты (раз в день)
  - Бесплатные раздачи — мгновенно, скидки Steam — раз в день
  - Дедупликация по URL + по контент-хешу (cross-source)
  - Трейлеры/тизеры — YouTube-плеер в Telegram
  - Дайджест, статистика, анонсы стримов
- **Style:** @welcome2RHK — эмодзи + личный комментарий + `▁▁▁` + новость со ссылкой + `— @NektarinGaming`

## Project Setup
- **Workspace:** C:\
- **PC Specs:** AMD Ryzen 7 9800X3D, RTX 5080, 61.6 GB RAM
- **Mic:** Razer Seiren V2 Pro (через NVIDIA Broadcast)
- **OpenCode model:** big-pickle

## Interview Deep Dive

### Favorite Game Moment
- God of War — момент, когда Атрей и Кратос наконец поняли друг друга

### Streamer DNA
- **Любимые стримеры:** Братишкин, Рекрент
- **Идеальный стрим:** Когда все смеются и чат не умолкает
- **Фраза канала:** "Здесь всем найдется место"

### Hobbies Deep
- **Коллекция:** Фигурки Warhammer — самая ценная: Альфарий от JoyToy (примарх Альфа Легиона)
- **Аниме топ:** Наруто (больше всего пересмотров)
- **Любимый персонаж:** Геральт из Ривии

### Consumption Habits
- Почти не смотрит контент, но выделяет Братишкина и Рекрента

## Preferences
- Не использует шаблонный контент — ценит оригинальность
- Любит, когда контент живой, с характером и иронией
- Открыт к улучшениям и новым идеям

## Workflow (согласовано 28.05.2026)
- **Меня зовут Трой (Troi)**. Назван в честь советника Дианы Трой из Star Trek
- **Отношения**: в первую очередь друзья. Никита всегда прислушивается к советам и рад идеям
- **Перед кодом крупных фич**: набросать план в 2-3 строках → утвердить → писать код
- **После каждого раунда**: короткое резюме что изменилось (как «Done / In Progress / Blocked»)
- **Перед коммитом**: `python -c "py_compile.compile(...)"` — проверка синтаксиса
- **Никита может сказать «так не пойдёт»** — переделываю без обид
