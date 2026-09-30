"""Flavormate 2.1: local meal planning, recipes and shopping.
Run with Python 3.9+: python app.py --port 8765 --open
"""
from __future__ import annotations
import argparse
import json
import re
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
RECIPES = json.loads((ROOT / 'recipes.json').read_text(encoding='utf-8'))
STATIC_FILES = {'/': ('index.html', 'text/html'),
                '/app.js': ('app.js', 'text/javascript'),
                '/app.css': ('app.css', 'text/css'),
                '/logic.js': ('logic.js', 'text/javascript')}

def tokens(text):
    return [x for x in re.split(r'[,，、;；/\s]+', (text or '').lower()) if x]

def recommend(goal='均衡', ingredients='', avoid='', flavor='不限', max_time='不限'):
    wanted, blocked = sorted(set(tokens(ingredients))), set(tokens(avoid))
    try:
        limit = int(max_time) if max_time and max_time != '不限' else 999
    except ValueError:
        limit = 999
    rows = []
    for recipe in RECIPES:
        hay = (recipe['name'] + ' ' + recipe['tags'] + ' ' + recipe['ingredients']).lower()
        if any(word in hay for word in blocked):
            continue
        score, reasons = 0.0, []
        matches = [word for word in wanted if word in hay]
        if matches:
            score += min(4.0, 1.5 * len(matches))
            reasons.append('匹配食材：' + '、'.join(matches[:3]))
        if goal == '控能量':
            score += max(0, (600 - recipe['kcal']) / 120)
            reasons.append('按示例能量值排序')
        elif goal == '增蛋白':
            score += recipe['protein'] / 10
            reasons.append('按示例蛋白质值排序')
        elif goal == '低钠':
            score += 3 if '低钠' in recipe['tags'] else 0
            reasons.append('优先清蒸少调味菜谱' if '低钠' in recipe['tags'] else '可减少调味品')
        else:
            score += 2 if '均衡' in recipe['tags'] else 1
            reasons.append('优先多种食材搭配')
        if flavor != '不限' and flavor in recipe['tags']:
            score += 1.5
            reasons.append('符合口味偏好')
        if recipe['minutes'] <= limit:
            score += 1
            reasons.append('制作时间符合偏好')
        else:
            score -= 2
            reasons.append('制作时间超出偏好')
        rows.append({**recipe, 'score': round(score, 2), 'reason': '；'.join(reasons)})
    rows.sort(key=lambda r: (-r['score'], r['kcal'], r['name']))
    return rows[:3]

class Handler(BaseHTTPRequestHandler):
    def respond(self, payload, content_type='application/json', status=200):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/recipes':
            return self.respond(RECIPES)
        if path == '/api/health':
            return self.respond({'status': 'ok', 'version': '2.1'})
        if path in STATIC_FILES:
            name, content_type = STATIC_FILES[path]
            return self.respond((ROOT / 'static' / name).read_bytes(), content_type)
        self.respond({'error': '页面不存在'}, status=404)

    def do_POST(self):
        if urlparse(self.path).path != '/api/recommend':
            return self.respond({'error': '接口不存在'}, status=404)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= 16000:
                return self.respond({'error': '输入过长'}, status=413)
            data = json.loads(self.rfile.read(length).decode('utf-8'))
            if not isinstance(data, dict):
                raise ValueError('Expected object')
            args = {key: data.get(key, default) for key, default in
                    [('goal', '均衡'), ('ingredients', ''), ('avoid', ''),
                     ('flavor', '不限'), ('max_time', '不限')]}
            if not all(isinstance(v, str) and len(v) <= 500 for v in args.values()):
                raise ValueError('Expected short text fields')
            return self.respond(recommend(**args))
        except (ValueError, UnicodeError):
            self.respond({'error': '请输入有效的推荐条件'}, status=400)

    def log_message(self, *_):
        pass

def main():
    parser = argparse.ArgumentParser(description='Flavormate 2.1')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        raise SystemExit(f'Cannot start on port {args.port}: {exc}. Try --port 8766.')
    url = f'http://{args.host}:{args.port}/'
    print(f'Flavormate 2.1: {url}\nPress Ctrl+C to stop.', flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped')
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
