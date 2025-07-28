import socket, ssl
import threading
import json
import sys
from uuid import uuid4
from sys import argv
from colorama import init as colorama_init
from colorama import Fore, Style
from typing import Optional
from flask import Flask, request
from flask import jsonify
# from flask_mysqldb import MySQL
import bcrypt
from datetime import datetime, timedelta
import base64

FORMAT = 'utf-8'
FORMAT = 'utf-8'
DRONE_COUNT = 0
R = f"{Style.RESET_ALL}"
LISTENING = f"{Fore.CYAN}{Style.BRIGHT}[LISTENING]{R}"
STARTING = f"{Fore.GREEN}{Style.BRIGHT}[STARTING]{R}"
SHUTDOWN = f"{Fore.RED}{Style.BRIGHT}[SHUTDOWN]{R}"
ERROR = f"{Fore.RED}{Style.BRIGHT}[SHUTDOWN]{R}"
NEWCON = f"{Fore.CYAN}{Style.BRIGHT}[NEW CONNECTION]{R}"
MISSING = f"{Fore.RED}{Style.BRIGHT}[MISSING]{R}"

KEY_FILE = './cert/key'
CERT_FILE = './cert/cert'


colorama_init()

app = Flask(__name__)
""" app.config['MYSQL_HOST'] = 'localhost'

app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'SD2023'
app.config['MYSQL_DB'] = 'registry'
mysql = MySQL(app) """
BBDD_FILE = "/app/drone_data/drones.json"

def getOwnIP():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

def msgWrap(msg:str):
  
    msg = msg.encode(FORMAT)
    lrc = msg[0]
    for c in msg[1:]:
        lrc = lrc ^ c
    return b'\x02' + msg + b'\x03' + str(lrc).encode(FORMAT)
 
def msgUnwrap(msg) -> Optional[str]:
 
    read = ''
    for i,c in enumerate(msg[1:]):
        if msg[i+1] == 3:
            read_lrc = msg[i+2:]
            break
        read += chr(c)

    read = read.encode(FORMAT)
    lrc = read[0]
    for c in read[1:]:
        lrc = lrc ^ c

    if lrc == int(read_lrc):
        return str(read, FORMAT)     
    return None

def generateToken():
    return str(uuid4())

def handleDrone(conn, addr):
    print(f"{NEWCON}{Fore.CYAN} Drone at {Style.BRIGHT}{addr[0]}:{addr[1]}{Style.NORMAL} connected.{R}")
    
    dataReceived = msgUnwrap(conn.recv(1024))
    registrationData = json.loads(dataReceived)
    # {"ID":ID, "Alias":Alias}

    data = []

    try:
        with open(BBDD_FILE, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        data = dict()
    except json.JSONDecodeError as e:
        data = dict()
    
    # drone is already registered
    try:
        conn.send(msgWrap("TOKEN " + data[registrationData["ID"]]["token"]))
        conn.close()
        return
    except KeyError:
        pass
    
    token = generateToken()

    registrationData["token"] = token
    droneID = registrationData["ID"]
    droneAlias = registrationData["Alias"]
    
    encrypted_alias = bcrypt.hashpw(droneAlias.encode('utf-8'), bcrypt.gensalt())
    encrypted_token = bcrypt.hashpw(token.encode('utf-8'), bcrypt.gensalt())
    token_expiry = datetime.now() + timedelta(seconds=20)  # Fija la caducidad del token
    
    # Convertir bytes a base64 para que sean serializables en JSON
    encrypted_alias_b64 = base64.b64encode(encrypted_alias).decode('utf-8')
    encrypted_token_b64 = base64.b64encode(encrypted_token).decode('utf-8')

    # Añade la nueva entrada al diccionario
    data[droneID] = {
        "Alias": encrypted_alias_b64,
        "token": encrypted_token_b64,
        "expiry": str(token_expiry)
    }

    #print("Editing Database... " + BBDD_FILE)
    with open(BBDD_FILE, 'w') as file:
        json.dump(data, file, indent= 4)
    
    #print("Sending Result...")
    msg = "TOKEN " + str(token)
    conn.send(msgWrap(msg))
    print(f"{Fore.GREEN}{Style.BRIGHT}Drone registered. Sending token to {Fore.MAGENTA}{droneID}:{droneAlias}...{R}")
    global DRONE_COUNT
    DRONE_COUNT += 1
    conn.close()

def startADRegistry():
    try:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(CERT_FILE, KEY_FILE)
        
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(ADDR)
        server.listen()
        
        print(f"{LISTENING}{Fore.CYAN} Waiting for drones at {Fore.YELLOW}{Style.BRIGHT}{ADDR[0]}:{ADDR[1]}{R}")
        while True:
            newsocket, fromaddr = server.accept()
            connstream = ssl_context.wrap_socket(newsocket, server_side=True)
            try:
                thread = threading.Thread(target=handleDrone, args=(connstream, fromaddr))
                thread.start()
                thread.join()
                print(f"{Fore.MAGENTA}Online drones: {Style.BRIGHT}[{DRONE_COUNT}]{R}")

            except Exception as e:
                print(f"An error has occurred during registration: {e}")
                connstream.shutdown(socket.SHUT_RDWR)
                connstream.close()
    except KeyboardInterrupt:
        print(f"\r{SHUTDOWN}")
        try:
            connstream.shutdown(socket.SHUT_RDWR)
            connstream.close()
            server.shutdown(socket.SHUT_RDWR)
            server.close()
        except:
            pass
        sys.exit()

@app.route('/index')
def index():
    return "Hello, I am the Registry!"

@app.route('/add_drone', methods=['POST'])
def add_drone():
    try:
        # Get the JSON data from the request
        data = request
        datas = request.get_json()
        print (datas)
        
        # Extract the 'alias' and 'token' fields from the JSON data
        droneID = datas['ID']
        droneAlias = datas['Alias']
        token = generateToken()
        print(f"{Fore.BLUE}{Style.BRIGHT}{token}{R}")
        encrypted_alias = bcrypt.hashpw(droneAlias.encode('utf-8'), bcrypt.gensalt())
        encrypted_token = bcrypt.hashpw(token.encode('utf-8'), bcrypt.gensalt())
        token_expiry = datetime.now() + timedelta(seconds=20)  # Fija la caducidad del token
        
        # Convert from bytes to base64 in order to be serializables in JSON
        encrypted_alias_b64 = base64.b64encode(encrypted_alias).decode('utf-8')
        encrypted_token_b64 = base64.b64encode(encrypted_token).decode('utf-8')
    
        try:
            with open(BBDD_FILE, 'r') as file:
                drones_db = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            drones_db = {}

        drones_db[droneID] = {
            "Alias": encrypted_alias_b64,
            "token": encrypted_token_b64,
            "expiry": str(token_expiry)
        }
        
        with open(BBDD_FILE, 'w') as file:
            json.dump(drones_db, file, indent=4)
        
        response_data = {
            'ID': datas['ID'], 
            'Alias': datas['Alias'],
            'token': token,
        }
        response = {
            'error' : False,
            'message': 'Drone Added Successfully',
            'data': response_data  
        }
        
        # Return a JSON response with HTTP status code 201 (Created)
        return jsonify(response), 200
    except Exception as e:
        # Handle any exceptions that may occur during the process
        response = {
            'error' : True,
            'message': f'Error Ocurred: {e}',
            'data': None
        }
        # Return a JSON response with HTTP status code 500 (Internal Server Error)
        return jsonify(response), 500

#? ####  MAIN ######
print(f"{STARTING}{Fore.GREEN} Initializing [AD_REGISTRY]{R}")
try:
    if len(argv) == 2:
        
        SERVER = getOwnIP()
        ADDR = (SERVER, int(argv[1]))
    else:
        print(MISSING, "MISSING ARGUMENT. AD_Registry receives arguments: <hosting port>")
        SERVER = getOwnIP()
        ADDR = (SERVER, 8082)
        #! exit()

    if __name__ == "__main__":
        api_thread = threading.Thread(target=lambda:
            app.run(host=SERVER,
                    port=5001,
                    use_reloader=False,
                    ssl_context=(
                        CERT_FILE,
                        KEY_FILE)))
        api_thread.start()
        
        socket_thread = threading.Thread(target=startADRegistry)
        socket_thread.start()
        
        api_thread.join()
        socket_thread.join()

except Exception as e:
    print(ERROR, e)