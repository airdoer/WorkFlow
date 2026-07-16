import sys

# Read base64
with open('client/deploy/logo_base64.txt', 'r') as f:
    b64 = f.read().strip()

# Read HTML
with open('client/deploy/bundle-status.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace logo src
html = html.replace('src="/logo1.png"', 'src="' + b64 + '"')

# Replace text
html = html.replace('<title>WorkFlow Studio — 编译中...</title>', '<title>WorkFlow Studio — 编编编译中……</title>')
html = html.replace('<h3>编译中...</h3>', '<h3>编编编译中……</h3>')

# Write back
with open('client/deploy/bundle-status.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('OK - replaced logo and text')
