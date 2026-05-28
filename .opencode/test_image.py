import requests, sys
sys.argv = ['test']
exec(open(r'C:\Users\La Vida Loca\.opencode\gaming_news_bot.py', encoding='utf-8').read().split('if __name__')[0])

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

