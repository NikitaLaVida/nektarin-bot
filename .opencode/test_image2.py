# -*- coding: utf-8 -*-
import sys
sys.argv = ['test']
exec(open(r'C:\Users\La Vida Loca\.opencode\gaming_news_bot.py', encoding='utf-8').read().split('if __name__')[0])

# Russian titles from actual feeds
titles = [
    'В сети появились новые скриншоты замка из Elden Ring',
    'Elden Ring — новый патч вышел',
    'В Witcher 4 найдена пасхалка',
]

for t in titles:
    game = extract_game(t)
    img = steam_image(game)
    print(f'{t[:35]:35s} -> game={game!r:25s} -> img={img is not None}')
    if not img:
        wiki = wiki_image(game)
        print(f'  wiki={wiki is not None}')
