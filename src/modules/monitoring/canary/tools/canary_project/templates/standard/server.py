from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "canary-api"})


@app.route('/api/.env', methods=['GET'])
def env_route():
    payload = "APP_ENV=production\\nAPP_SECRET=canary-secret\\nDATABASE_URL=postgres://app:secret@db:5432/app\\n"
    return payload, 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route('/config/app.env', methods=['GET'])
def config_route():
    payload = "APP_ENV=production\\nLOG_LEVEL=debug\\nUPLOAD_DIR=/var/tmp/uploads\\n"
    return payload, 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route('/admin/.env', methods=['GET'])
def admin_env():
    payload = "APP_ENV=production\\nADMIN_EMAIL=ops@example.internal\\nADMIN_USER=admin\\n"
    return payload, 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route('/public/index.php', methods=['GET'])
def index_php():
    return "<?php echo 'canary service ready'; ?>", 200, {"Content-Type": "application/x-httpd-php"}


@app.route('/wp-config.php', methods=['GET'])
def wp_config():
    return "<?php\\n// WordPress canary stub\\n$database_name = 'wordpress';\\n?>", 200, {"Content-Type": "application/x-httpd-php"}


@app.route('/phpmyadmin/index.php', methods=['GET'])
def phpmyadmin():
    return "<html><body>phpMyAdmin canary stub</body></html>", 200, {"Content-Type": "text/html; charset=utf-8"}


@app.before_request
def log_request():
    metadata = {
        'method': request.method,
        'path': request.path,
        'remote_addr': request.remote_addr,
        'user_agent': request.user_agent.string,
        'host': request.headers.get('Host', ''),
    }
    with open('/tmp/canary-access.log', 'a', encoding='utf-8') as handle:
        handle.write(str(metadata) + '\\n')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
