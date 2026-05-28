import sqlite3, os

cookie_path = r'C:\Users\La Vida Loca\AppData\Local\Yandex\YandexBrowser\User Data\Default\Network\Cookies'
if os.path.exists(cookie_path):
    print(f'Cookies file exists: {cookie_path}')
    print(f'Size: {os.path.getsize(cookie_path)}')
    try:
        conn = sqlite3.connect(cookie_path)
        cursor = conn.cursor()
        result = cursor.execute("SELECT host_key, name FROM cookies WHERE host_key LIKE '%music%'").fetchall()
        print(f'Music cookies: {result}')
        result2 = cursor.execute("SELECT host_key, name, value FROM cookies WHERE host_key LIKE '%yandex%' AND name LIKE '%token%'").fetchall()
        print(f'Token cookies: {result2}')
        result3 = cursor.execute("SELECT host_key, name FROM cookies WHERE host_key LIKE '%yandex%'").fetchall()
        print(f'All Yandex cookies ({len(result3)}): {result3[:20]}')
        conn.close()
    except Exception as e:
        print(f'Error reading cookies: {e}')
else:
    print(f'File not found: {cookie_path}')
    for root, dirs, files in os.walk(r'C:\Users\La Vida Loca\AppData\Local\Yandex\YandexBrowser\User Data'):
        if 'Cookies' in files:
            path = os.path.join(root, 'Cookies')
            print(f'Found: {path}')
