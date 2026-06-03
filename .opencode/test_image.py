import sys
sys.argv = ['test']
from bot.core import extract_game
from bot.images import steam_image

titles = [
    'New screenshots of a castle from Elden Ring',
    'Elden Ring new patch released',
    "Witcher 4 found an easter egg",
    "Half-Life 3 confirmed",
    "The Verge article about GTA 6 leaks",
]
for t in titles:
    game = extract_game(t)
    img = steam_image(game)
    if img:
        print(f'OK: {t[:30]:30s} -> {game:15s} -> img')
    else:
        print(f'NO: {t[:30]:30s} -> {game:15s} -> no img')
print('Done')
