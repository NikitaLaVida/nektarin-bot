import sys
sys.argv = ['test']
from bot.core import extract_game
from bot.images import steam_image, wiki_image

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
        w = wiki_image(game)
        print(f'  wiki={w is not None}')
