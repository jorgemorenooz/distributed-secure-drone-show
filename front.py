from flask import Flask, send_file
from flask_mysqldb import MySQL
import socket
from flask import Flask, send_from_directory

FORMAT = 'utf-8'

app = Flask(__name__)
app.config['MYSQL_HOST'] = 'localhost'

app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'SD2023'
app.config['MYSQL_DB'] = 'registry'
mysql = MySQL(app)

def getOwnIP():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


@app.route('/front')
def front():
    return send_file('index.html')

@app.route('/img/<filename>')
def get_image(filename):
    return send_from_directory('../img', filename)


@app.route('/favicon.ico')
def favicon():
    return 200
      
if __name__ == "__main__":
    app.debug = False
    app.run(
        host=getOwnIP(), port=5004,
        ssl_context=(
            './certificados/certificado_registry.crt',
            './certificados/clave_privada_registry.pem'))
