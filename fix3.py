import pathlib, json

p = pathlib.Path(r'c:\Users\USER\Downloads\sample\app.py')
text = p.read_text(encoding='utf-8')
text = text.replace('height:72px;text-align:center', 'min-height:72px;text-align:center')
p.write_text(text, encoding='utf-8')

text2 = p.read_text(encoding='utf-8')
if 'min-height:72px' in text2:
    print('OK: min-height applied')
else:
    print('FAIL: min-height not found')

h = json.loads(pathlib.Path(r'c:\Users\USER\Downloads\sample\school_holidays.json').read_text(encoding='utf-8'))
for v in h['2025']['school_vacations']:
    print(v['text'], v['start'], v['end'])
