import socket
import threading
import json
from os import path, makedirs
from sys import argv
from time import sleep, time
from kafka import KafkaConsumer, KafkaProducer, TopicPartition
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from colorama import init as colorama_init
from colorama import Fore, Style
from getpass import getpass
from typing import Optional
from AD_Display import Display
from flask import Flask, request
from flask import jsonify
# from flask_mysqldb import MySQL
from flask_cors import CORS
import requests
from datetime import datetime
import ssl
from cryptography.fernet import Fernet
import bcrypt
import base64
import logging
colorama_init()

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

FORMAT = 'utf-8'
KEY_FILE = './cert/private_key_engine.pem'
CERT_FILE = './cert/certificate_engine.crt'
OPEN_WEATHER_KEY = '000000'
temperature = 0
new_logs  = []

R = f"{Style.RESET_ALL}"
ALLSET = f"{Fore.GREEN}{Style.BRIGHT}[ALL SYSTEMS SET]{R}"
MISSING = f"{Fore.RED}{Style.BRIGHT}[MISSING]{R}"
LISTENING = f"{Fore.CYAN}{Style.BRIGHT}[LISTENING]{R}"
STARTING = f"{Fore.GREEN}{Style.BRIGHT}[STARTING]{R}"
SHUTDOWN = f"{Fore.RED}{Style.BRIGHT}[SHUTDOWN]{R}"
WEATHER_ALERT = f"{Fore.MAGENTA}{Style.BRIGHT}[WEATHER ALERT]{R}"
SHOW_START = f"{Fore.CYAN}{Style.BRIGHT}[SHOW START]{R}"
NEW_CONNECTION = f"{Fore.MAGENTA}{Style.BRIGHT}[NEW CONNECTION]{Style.NORMAL}{R}"
NEW = f"{Fore.GREEN}{Style.BRIGHT}[NEW]{R}"
ERROR = f"{Fore.RED}{Style.BRIGHT}[ERROR]{R}"
NEWCON = f"{Fore.CYAN}{Style.BRIGHT}[NEW CONNECTION]{R}"

app = Flask(__name__)
""" app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'SD2023'
app.config['MYSQL_DB'] = 'registry'
mysql = MySQL(app) """
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

def getOwnIP():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

#! def main()
if len(argv) >=4:
        
    SERVER = getOwnIP()
    ADDR = (SERVER, int(argv[1]))
    DRONE_MAX = int(argv[2])
    broker = argv[3].split(':', 2)
    BROKER_ADDR = (broker[0], int(broker[1]))
    ASSIGN_FREELY = len(argv) == 6 and argv[4] == '--free'

    DB_FILE = 'drone_credentials.json'
    SOCK_FORMAT = 'utf-8'
    FIG_FILE = 'figures.json'
    DRONE_RECOVERY = './drone_recovery'
    WEATH_REPLY_SIZE = 1024

    WEATHER_SECS = 1    # how often to ask for weather update
    DISCONNECT_SECS = 3 # how long before connection considered lost
    DRONE_SECS = 5.0      # how long for a drone to be considered dead

    KTOPIC_MOVES = 'droneMoves'
    KTOPIC_ORDERS = 'droneOrders'
    KTOPIC_BOARDS = 'droneBoards'

    READY = False
    PERFORMING = {}
    SHOW_IN_ACTION = False
    DRONE_COUNT = 0     # Authenticated drones
    ALIVE_DRONES = 0    # Authenticated drones with active conection
    READY_DRONES = 0    # Drones which arrived to its final position
    DRONES_WITH_POS = []
    REPLACEMENT_DRONES = {}
    
    BOARD = dict()
    FIGURES = list()
    DRONES = dict()

    SHUTDOWN_SYSTEM = False

else:
    print(ERROR,"MISSING ARGUMENT. AD_Engine receives arguments: <hosting port> <max_drones> <broker IP:port>")
    exit()

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

def register_event(accion, descripcion, ip):
    global new_logs
    filepath = path.join('./log', f"events.log")
    
    if not path.exists('./log'):
        makedirs('./log')

    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    event = f"{date} - IP: {ip}, Event: {accion}, Description: {descripcion}\n"
    
    with open(filepath, 'a') as archivo:
        archivo.write(event)
    
    new_logs.append(event)
    
################################
#  KEEP TRACK OF FIGURE FILE   #
################################

class FiguraCambiadaHandler(FileSystemEventHandler):
    
    def __init__(self):
        self.timestamp = time()
        self.load_figures()
        
    def load_figures(self):
        global FIGURES
        if not path.exists(FIG_FILE):
            print(f"[WARNING] Figure file '{FIG_FILE}' not found. No figures loaded.")
            FIGURES = []
            return

        try:
            with open(FIG_FILE, 'r') as f:
                data = json.load(f)
                if "figuras" in data and isinstance(data["figuras"], list):
                    FIGURES = data["figuras"]
                    figNames = [x["Nombre"] for x in FIGURES]
                    print(f"{NEW} Loaded figure list: {Fore.YELLOW}{Style.BRIGHT}{' · '.join(figNames)}{R}")
                else:
                    print("[WARNING] 'figuras' key missing or not a list. File ignored.")
                    FIGURES = []
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse '{FIG_FILE}': {e}")
            FIGURES = []
        except Exception as e:
            print(f"[ERROR] Unexpected error loading figures: {e}")
            FIGURES = []

    def on_modified(self, event):
        if time() - self.timestamp > 3 and event.src_path.endswith(FIG_FILE):
            self.timestamp = time()
            self.load_figures()

            figNames = [x["Nombre"] for x in FIGURES]
            
            print(f"{NEW} New schedule added with the following figures: {Fore.YELLOW}{Style.BRIGHT}{' · '.join(figNames)}{R}")
            register_event('Figure added', f"new figure added: {figNames}", 'localhost')

    def on_created(self, event):
        if time() - self.timestamp > 3 and event.src_path.endswith(FIG_FILE):
            self.timestamp = time()
            self.load_figures()

            figNames = [x["Nombre"] for x in FIGURES]
            
            print(f"{NEW} New schedule added with the following figures: {Fore.YELLOW}{Style.BRIGHT}{' · '.join(figNames)}{R}")
            register_event('Figure added', f"new figure added: {figNames}", 'localhost')
            
#!###### CLAVE SIMETRICA ############

def encode_message(message, symetric_key):
    try:
        fernet = Fernet(symetric_key)
        encoded_message = fernet.encrypt(message.encode())
    except Exception:
        symetric_key = Fernet.generate_key()
        fernet = Fernet(symetric_key)
        encoded_message = fernet.encrypt(message.encode())
    return encoded_message.decode(FORMAT)

def decode_message(encoded_message, symetric_key):
    try:
        fernet = Fernet(symetric_key)
    except Exception:
        symetric_key = Fernet.generate_key()
        fernet = Fernet(symetric_key)
    
    try:
        message_raw = encoded_message.decode('utf-8')
        decoded_message = fernet.decrypt(message_raw)
        
        return [json.loads(decoded_message), True]
    
    except Exception:
        
        return [None, False]

def save_symetric_key(id_dron, key):
    
    filepath = path.join('./keys_Engine', f"{id_dron}.txt")
    
    if not path.exists('./keys_Engine'):
        makedirs('./keys_Engine')
        
    with open(filepath, 'w') as file:
        file.write(str(key.decode('utf-8')))
        
    sleep(1)

def load_symetric_key(id_dron):
    
    filepath = path.join('./keys_Engine', f"{id_dron}.txt")
    
    try:
        with open(filepath, 'r') as file:
            return file.read()
    except Exception as e:
        return Fernet.generate_key()

#!###################################

################################
#     authenticate drones      #
################################

def authDrone(conn, addr):
    global BOARD
    print(f"{NEWCON}{Fore.CYAN} Drone at {Style.BRIGHT}{addr[0]}:{addr[1]}{Style.NORMAL} connected.{R}")
    register_event('New connection',
                    f"Drone",
                    f"{addr[0]}:{addr[1]}")
    # qué tipo de mensaje es
    try:
        dataReceived = msgUnwrap(conn.recv(1024))
        data = json.loads(dataReceived)
        idSent = data["ID"]
        aliasSent = data["alias"]
        tokenSent = data["token"]
    except (json.decoder.JSONDecodeError, IndexError, KeyError):
        conn.send(msgWrap(f"0"))
        return

    try:
        with open(DB_FILE, 'r') as file:
            datosDrones = json.load(file)
    except FileNotFoundError:
        datosDrones = dict()
    
    tokenDB = datosDrones[idSent]["token"]
    token_expiry_str = datosDrones[idSent]["expiry"]
    token_expiry = datetime.strptime(token_expiry_str, "%Y-%m-%d %H:%M:%S.%f")
    
    if datetime.now() > token_expiry:
        print(f"{NEW_CONNECTION}{Fore.MAGENTA} Drone {idSent}:{aliasSent} {Fore.RED}{Style.BRIGHT}Token expirado.{R}")
        register_event('Authentication',
                        f"Authentication failed, token expired",
                        f"{addr[0]}:{addr[1]}")
        
        conn.send(msgWrap(f"0"))
    else:
        hashed_token = base64.b64decode(tokenDB.encode('utf-8'))

        if bcrypt.checkpw(tokenSent.encode('utf-8'), hashed_token):
            global PERFORMING
            
            clave_simetrica = Fernet.generate_key()
            print('Clave simetrica: ', clave_simetrica)
            save_symetric_key(idSent, clave_simetrica)
            
            if idSent in DRONES:
                
                if (BOARD[idSent]["status"] == 'X') or (BOARD[idSent]["status"] == 'N' and SHOW_IN_ACTION):
                    print(f"{NEW_CONNECTION}{Fore.MAGENTA} Drone {idSent}:{aliasSent} has reestablished connection.{R}")
                    register_event('Authentication',
                            f"Authentication from Drone {idSent} successful (2)",
                            f"{addr[0]}:{addr[1]}")
                    
                    partition = DRONES[idSent]["partition"]
                    pos_recovery = BOARD[idSent]["POS"]
                    
                    conn.send(msgWrap(f"2 {partition} {pos_recovery} {clave_simetrica.decode()}"))
                    conn.close()
                    sleep(1) #Para que guarde la clave simetrica
                    
                    PERFORMING[idSent] = {"status": False, "position": pos_recovery}
                    
                else:
                    print(f"{NEW_CONNECTION}{Fore.MAGENTA} Drone {idSent}:{aliasSent} has reestablished connection.{R}")
                    register_event('New connection',
                                    f"Drone ha reestablecido la conexion",
                                    f"{addr[0]}:{addr[1]}")
                    
                    partition = DRONES[idSent]["partition"]
                    conn.send(msgWrap(f"1 {partition} {clave_simetrica.decode()}"))
                    conn.close()

                    return

            global DRONE_COUNT, ALIVE_DRONES
            
            # Inicializar el estado y la posicion del drone en el BOARD
            BOARD[idSent] = {"status": 'N', "POS": [0, 0]}
            
            particion_asignada = (int(idSent) - 1)
            DRONES[idSent] = dict()
            DRONES[idSent]["partition"] = particion_asignada
            DRONES[idSent]["alias"] = aliasSent

            print(f"{NEW_CONNECTION}{Fore.MAGENTA} Drone {idSent}:{aliasSent} {Fore.GREEN}{Style.BRIGHT}authenticated (1).{R}")
            
            register_event('Authentication',
                            f"Authentication de  Drone {idSent} exitosa (1)",
                            f"{addr[0]}:{addr[1]}")
            
            conn.send(msgWrap(f"1 {idSent-1} {clave_simetrica.decode()}"))

            consumerCoordinates = KafkaConsumer(
                bootstrap_servers=[argv[3]],
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='engine',
                value_deserializer=lambda x: decode_message(x, load_symetric_key(idSent))
            )

            consumerCoordinates.assign([TopicPartition(KTOPIC_MOVES, DRONES[idSent]["partition"])])
            
            #! Para leer mensajes que quedaron obsoletos
            try:
                consumerCoordinates.poll(timeout_ms=1000)
                consumerCoordinates.seek_to_end()
            except Exception:
                pass
            
            PERFORMING[idSent] = {"status": False, "position": None}
            
            thread = threading.Thread(target=handleDrone, args=(consumerCoordinates,str(idSent)))
            thread.start()

            DRONE_COUNT += 1

        else:
            print(f"{NEW_CONNECTION}{Fore.MAGENTA} Drone {idSent}:{aliasSent} {Fore.RED}{Style.BRIGHT}failed to authenticate.{R}")
            register_event('Authentication',
                            f"Authentication from Drone {idSent} failed",
                            f"{addr[0]}:{addr[1]}")
            
            conn.send(msgWrap(f"0"))
    
def authDrone_setup():
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(CERT_FILE, KEY_FILE)
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(ADDR)
    server.listen(DRONE_MAX+1)
    
    print(f"{LISTENING} Waiting for drones on {Fore.YELLOW}{Style.BRIGHT}{ADDR[0]}:{ADDR[1]}{R}")
   
    try:
        while not SHUTDOWN_SYSTEM:

            newsocket, fromaddr = server.accept()
            connstream = ssl_context.wrap_socket(newsocket, server_side=True)
            try:
                if(DRONE_COUNT < DRONE_MAX):
                    thread = threading.Thread(target=authDrone, args=(connstream, fromaddr))
                    thread.start()
                    thread.join()
                else:
                    print(f"{Style.DIM}{Fore.CYAN}Drone attempted connection, but was rejected because there are no slots left.{R}")
                    register_event('Sockets Engine',
                                    f"conexion ha sido rechazada",
                                    f"{fromaddr[0]}:{fromaddr[1]}")
                    
                    connstream.shutdown(socket.SHUT_RDWR)
                    connstream.send("wait".encode(SOCK_FORMAT))
                    
                connstream.close()

            except Exception as e:
                print(f"{ERROR} An error has occurred during registration: {e}")
                register_event('Sockets Engine',
                                f"Error Inesperado {e}",
                                f"{fromaddr[0]}:{fromaddr[1]}")
                connstream.shutdown(socket.SHUT_RDWR)
                connstream.close()
                
    except OSError as e:
        # probably ctrl+c interrupted server.accept
        pass
    except Exception as e:
        print(f"An unexpected exception occured while listening for drone connection -> {str(e)}")
        register_event('Sockets Engine',
                        f"Error Inesperado {e}",
                        f"{fromaddr[0]}:{fromaddr[1]}")
        raise e

################################
#           ORDERS             #
################################

def dronesJOIN():

    global READY_DRONES, BOARD, PERFORMING, DRONES_WITH_POS, SHOW_IN_ACTION
    READY_DRONES = 0
    
    for id in DRONES:
        if id not in BOARD:
            BOARD[id] = {"status": 'N', "POS": [0, 0]}

    try:
        if READY_DRONES < len(figure):
            print(f"{Fore.YELLOW}{Style.BRIGHT}The next figure requires {Fore.MAGENTA}{len(figure)}{Fore.YELLOW} drones, and we have {Fore.MAGENTA}{DRONE_COUNT}. {Fore.WHITE}Sure you wanna continue? (Y/N){R}")
            """ if input('>').upper() == 'N':
                print(f"{Fore.GREEN}{Style.BRIGHT}Skipped.{R}")
                return False """
    except NameError:
        # Esta es una llamada del weather antes de un espectaculo
        return

    if READY:
        SHOW_IN_ACTION = True
        #print(f"destinos: {destinos}")
        print(f"{SHOW_START}{Fore.CYAN} Sending {Style.BRIGHT}<JOIN>{Style.NORMAL} to drones...{R}")
        
        DRONES_WITH_POS = []
        PERFORMING = {drone_id: {"status": False, "position": [0,0]} for drone_id in DRONES}
        
        for id in DRONES:
            
            for order in destinos:

                if str(order) == str(id) or ASSIGN_FREELY:
                    #5 4
                    position = [destinos[order][0], destinos[order][1]]
                    
                    clave_simetrica = load_symetric_key(id)

                    # Preparar los datos para enviar
                    data = {"POS": f"{destinos[order][0]} {destinos[order][1]}"}
                    data_cifrada = encode_message(json.dumps(data), clave_simetrica)

                    # Enviar datos cifrados
                    droneOrdersProd.send(KTOPIC_ORDERS, value=data_cifrada, partition=DRONES[id]["partition"])
                    droneOrdersProd.flush()
                    DRONES_WITH_POS.append(id)
                    
                    PERFORMING[id] = {"status": True, "position": position}
        
        for id in DRONES:
            if id not in DRONES_WITH_POS:
                base = [0,0]
                BOARD[id]["status"] = 'Y'
                
                clave_simetrica = load_symetric_key(id)

                # Preparar los datos para enviar
                data = {"POS": f"{base[0]} {base[1]}"}
                data_cifrada = encode_message(json.dumps(data), clave_simetrica)

                # Enviar datos cifrados
                droneOrdersProd.send(KTOPIC_ORDERS, value=data_cifrada, partition=DRONES[id]["partition"])
                droneOrdersProd.flush()
                
                PERFORMING[id] = {"status": False, "position": base}

        while not SHUTDOWN_SYSTEM:
            if not READY:
                READY_DRONES = 0
                return

            if READY_DRONES == ALIVE_DRONES:
                SHOW_IN_ACTION = False
                print(f"{Fore.CYAN}{Style.BRIGHT}Figure finished. Look at that!{R}")
                register_event('Espectaculo',
                        f"Figura terminada {figure}",
                        f"127.0.0.1")
                sleep(1)
                print("          3", end="\r") 
                sleep(1) 
                print("          2", end="\r") 
                sleep(1) 
                print("          1", end="\r")
                sleep(1)

                READY_DRONES = 0
                return

def dronesRETREAT():

    global READY, PERFORMING, BOARD
    READY = False
    print(f"{WEATHER_ALERT} {Fore.RED}Sending {Style.BRIGHT}<RETREAT>{Style.NORMAL} to drones...{R}")
    register_event('Espectaculo',
                        f"Enviando RETREAT",
                        f"127.0.0.1")
    PERFORMING = {drone_id: {"status": True, "position": [0,0]} for drone_id in DRONES}
    
    for id in DRONES:
        BOARD[id]["status"] = 'N'
        clave_simetrica = load_symetric_key(id)

        # Preparar los datos para enviar
        data = {"POS": f"0 0"}
        data_cifrada = encode_message(json.dumps(data), clave_simetrica)

        # Enviar datos cifrados
        droneOrdersProd.send(KTOPIC_ORDERS, value=data_cifrada, partition=DRONES[id]["partition"])
        droneOrdersProd.flush()

################################
#           WEATHER            #
################################

def get_API_key():
    try:
        with open('./openweather_key.txt', 'r') as file:
            return file.readline().strip()
    except FileNotFoundError:
        return '000000000'

def inputWeatherAPI(ciudad):
    global OPEN_WEATHER_KEY
    
    OPEN_WEATHER_KEY = get_API_key()
    
    base_url = "http://api.openweathermap.org/data/2.5/weather?"
    complete_url = base_url + "appid=" + OPEN_WEATHER_KEY + "&q=" + ciudad + "&units=metric"
    # http://api.openweathermap.org/data/2.5/weather?appid=07be57576b6924f8a389dfbada63e670&q=Alicante&units=metric
    response = requests.get(complete_url)
    return response.json()

def inputWeather():
    global READY, temperature
    while not SHUTDOWN_SYSTEM:
        try:
            
            with open('ciudades.json', 'r') as file:
                cities = json.load(file)
                city = cities['ciudades'][0]
                
            try:
                weather_data = inputWeatherAPI(city)
                temperature = weather_data["main"]["temp"]
                register_event('OpenWeather',
                            f"Temperatura registrada de {city}: {temperature}",
                            f"127.0.0.1")
            except Exception:
                temperature = 1
            READY = True
            try:
                if int(temperature) < 0:
                    print(f"{WEATHER_ALERT} {Fore.RED}Hace mucho frio! en {city}{Style.BRIGHT}[{temperature}]{Style.NORMAL}{R}")
                    dronesRETREAT()
            except Exception:
                pass

        except Exception as e:
            print(f"{MISSING}{Fore.RED} Error al obtener datos del clima: {e}.{R}")
            register_event('OpenWeather',
                            f"Error al obtener datos del clima: {e}",
                            f"148.251.136.139")
            dronesRETREAT()
        
        sleep(10) # 1 peticion cada 10 segundos

################################
#             SHOW             #
################################

def resetDroneStatus():
    global BOARD
    for drone_id in BOARD:
        if not BOARD[drone_id]["status"] == 'X':
            BOARD[drone_id]["status"] = 'N'

    clave_simetrica = load_symetric_key(id)
    data_cifrada = encode_message(json.dumps(BOARD), clave_simetrica)

    # Enviar datos cifrados
    droneBoardsProd.send(KTOPIC_BOARDS, value=data_cifrada)
    droneBoardsProd.flush()

def checkTime(timerStart, timeout):
    return (time() - timerStart) > timeout

def handleDrone(consumerCoordinates, id, forShow=True):
    global ALIVE_DRONES, BOARD, READY_DRONES, PERFORMING, DRONES_WITH_POS
    ALIVE_DRONES += 1

    # Establecer el estado inicial del drone en el BOARD
    if id not in BOARD:
        BOARD[id] = {"status": 'N', "POS": [0, 0]}

    pos = [0, 0]
    was_alive = True

    # Configurar el temporizador
    timeout = 5
    timerStart = time()
    try:
        while True:
            try:
                try:
                    consumerRecords = consumerCoordinates.poll(timeout_ms=1000)
                except Exception as e:
                    print(f"Error en poll(): {e}")
                
                if not consumerRecords:
                    
                    global REPLACEMENT_DRONES
                    
                    if PERFORMING[id]["status"] == True:
                        if checkTime(timerStart, timeout) and was_alive:
                            print(f"{MISSING}{Fore.MAGENTA}{Style.DIM} Drone {id} is missing.{R}")
                            register_event('Espectaculo',
                                            f"Drone {id} se ha perdido",
                                            f"127.0.0.1")
                            ALIVE_DRONES -= 1
                            BOARD[id]["status"] = 'X'
                            READY_DRONES-=1
                            was_alive = False
                            PERFORMING[id]["status"] = False
                            
                            #Mandar a uno de not in DRONES_WITH_POS
                            for dron_sustituto in DRONES:
                                if dron_sustituto not in DRONES_WITH_POS:
                                    destination = PERFORMING[id]["position"]
                                    
                                    data = {"POS": f"{destination[0]} {destination[1]}"}
                                    
                                    # Preparar los datos para enviar
                                    clave_simetrica = load_symetric_key(dron_sustituto)
                                    data_cifrada = encode_message(json.dumps(data), clave_simetrica)

                                    # Enviar datos cifrados
                                    droneOrdersProd.send(KTOPIC_ORDERS, value=data_cifrada, partition=DRONES[dron_sustituto]["partition"])
                                    droneOrdersProd.flush()
                                    
                                    PERFORMING[dron_sustituto] = {"status": True, "position": destination}
                                    DRONES_WITH_POS.append(dron_sustituto)
                                    REPLACEMENT_DRONES[id] = dron_sustituto
                                    BOARD[dron_sustituto]["status"] = 'N'
                                    
                                    break
                    else:
                        timerStart = time()
                    continue
                

                for record in consumerRecords.values():
                    for message in record:
                        exito = message.value[1]
                        if exito:
                            if not was_alive:
                                ALIVE_DRONES += 1
                                was_alive = True
                                register_event('Espectaculo',
                                                    f"Drone {id} ha vuelto",
                                                    f"127.0.0.1")
                                
                                if pos == [-1, -1]:
                                    BOARD[id]["status"] = 'Y'
                                else:
                                    BOARD[id]["status"] = 'N'

                            timerStart = time()
                            pos = message.value[0]["POS"]
                            if pos == [-1, -1]: #La recibe cuando el dron ha llegado a la pos
                                BOARD[id]["status"] = 'Y'
                                READY_DRONES+=1
                                PERFORMING[id]["status"] = False
                                #! Aqui no hace falta actualizar BOARD[id]["POS"]
                            
                            elif pos == [-2, -2]:
                                #La recibe cuando el dron se ha reconectado
                                #Devolver el Dron de reserva y pasarle la pos_Destino de vuelta
                                destination = PERFORMING[id]["position"]
                                data = {"POS": f"{destination[0]} {destination[1]}"}
                                
                                #Si estaba siendo sustituido
                                if id in REPLACEMENT_DRONES:
                                    dron_sustituto = REPLACEMENT_DRONES[id]
                                    data = {"POS": "0 0"}
                                    
                                    # Preparar los datos para enviar
                                    clave_simetrica = load_symetric_key(id)
                                    data_cifrada = encode_message(json.dumps(data), clave_simetrica)

                                    # Enviar datos cifrados
                                    droneOrdersProd.send(KTOPIC_ORDERS, value=data_cifrada, partition=DRONES[id]["partition"])
                                    droneOrdersProd.flush()
                                    PERFORMING[dron_sustituto] = {"status": False, "position": [0, 0]}
                                    
                                    # Eliminar la asignacion del dron de reemplazo
                                    del REPLACEMENT_DRONES[id]
                                    
                                clave_simetrica = load_symetric_key(id)
                                data_cifrada = encode_message(json.dumps(data), clave_simetrica)

                                # Enviar datos cifrados
                                sleep(1.5) #Para que no lleguen antes de que el dron procese la respuesta
                                droneOrdersProd.send(KTOPIC_ORDERS, value=data_cifrada, partition=DRONES[id]["partition"])
                                droneOrdersProd.flush()
                                print(f'Enviando a Drone {1} los datos {data}')
                                
                                PERFORMING[id]["status"] = True
                            
                            elif pos == [-3, -3]: #La recibe cuando el dron quiere checkear si el engine sigue vivo
                                data = {"POS": "-3 -3"}
                                # Preparar los datos para enviar
                                clave_simetrica = load_symetric_key(id)
                                data_cifrada = encode_message(json.dumps(data), clave_simetrica)

                                # Enviar datos cifrados
                                droneOrdersProd.send(KTOPIC_ORDERS, value=data_cifrada, partition=DRONES[id]["partition"])
                                droneOrdersProd.flush()
                                
                            else:
                                BOARD[id]["POS"] = pos
                                # Aqui no hace falta actualizar BOARD[id]["status"]
                            
                            display.update(BOARD)
                            
                            clave_simetrica = load_symetric_key(1)
                            data_cifrada = encode_message(json.dumps(BOARD), clave_simetrica)

                            # Enviar datos cifrados
                            droneBoardsProd.send(KTOPIC_BOARDS, value=data_cifrada)
                            droneBoardsProd.flush()
                        
                        else:
                            partition = message.partition  # Obtener la particion del mensaje
                            print(f"Drone {id} en la particion {partition}, No te entiendo, clave {load_symetric_key(id)}")
                            register_event('Error al descifrar mensaje',
                                            f"Drone {id}, No te entiendo",
                                            'localhost')
                            
                            ALIVE_DRONES -= 1
                            BOARD[id]["status"] = 'X'
                            was_alive = False
                            PERFORMING[id]["status"] = False
                            
                            if SHOW_IN_ACTION:
                                #Mandar a uno de not in DRONES_WITH_POS
                                for dron_sustituto in DRONES:
                                    if dron_sustituto not in DRONES_WITH_POS:
                                        destination = PERFORMING[id]["position"]
                                        print(f"{Fore.YELLOW} Enviando al Dron {dron_sustituto}{R}")
                                        data = {"POS": f"{destination[0]} {destination[1]}"}
                                        
                                        # Preparar los datos para enviar
                                        clave_simetrica = load_symetric_key(id)
                                        data_cifrada = encode_message(json.dumps(data), clave_simetrica)

                                        # Enviar datos cifrados
                                        droneOrdersProd.send(KTOPIC_ORDERS, value=data_cifrada, partition=DRONES[id]["partition"])
                                        droneOrdersProd.flush()
                                        
                                        PERFORMING[dron_sustituto] = {"status": True, "position": destination}
                                        DRONES_WITH_POS.append(dron_sustituto)
                                        REPLACEMENT_DRONES[id] = dron_sustituto
                                        BOARD[dron_sustituto]["status"] = 'N'
                                        
                                        break
                    

            except Exception as e:
                print("Error inesperado: ",e)
                register_event('Espectaculo',
                                f"Error inesperado: {e}",
                                f"127.0.0.1")
                continue
                    

    except KeyError as e:
        print("Ha ocurrido un error durante la lectura de los Drones: ",e)
        register_event('Espectaculo',
                            f"Ha ocurrido un error durante la lectura de los Drones: {e}",
                            f"127.0.0.1")
        
        pass
    except Exception as e:
        print("Error: ",e)
        register_event('Espectaculo',
                        f"Error: {e}",
                        f"127.0.0.1")
        pass

def printALLSET():
    print(f"{ALLSET}")
    print(f"{Fore.MAGENTA}{Style.DIM}Press {Style.NORMAL}ENTER{Style.DIM} to start. {Style.NORMAL}Ctrl+C{Style.DIM} to SHUTDOWN.{R}")
    getpass('')

def startADEngine():
    
    try:
        global droneOrdersProd, droneBoardsProd, display, observer, destinos, figure
        
        print(f"{STARTING}{Fore.GREEN} Initializing AD_Engine{R}")

        server.bind(ADDR)
        
        # Modifica FIGURES cuando hay un cambio en el archivo #
        # Funciona con un trigger #
        observer = Observer()
        observer.schedule(FiguraCambiadaHandler(), path='.')
        observer.start()

        # Establece un puerto servidor para autenticar drones # 
        # Cuando un dron se autentica se le asigna una particion en KTOPIC_MOVES
        authThread = threading.Thread(target=authDrone_setup)
        authThread.start()
        
        droneOrdersProd = KafkaProducer(bootstrap_servers=[argv[3]],
                                        value_serializer=lambda v: json.dumps(v).encode('utf-8'))
        
        droneBoardsProd = KafkaProducer(bootstrap_servers=[argv[3]],
                                        value_serializer=lambda v: json.dumps(v).encode('utf-8'))


        # Establece un puerto cliente para pedirle updates al weather #
        weatherThread = threading.Thread(target=inputWeather)
        weatherThread.start()

        display = Display()
        display.start()
        
        if not FIGURES:
            print(f"{ERROR} No figures loaded. Add a figure to '{FIG_FILE}' to start the show.")
            return
        
        figure = FIGURES[0]["Drones"]
        destinos = {str(a["ID"]):[int(x) for x in a["POS"].split(',')] for a in figure}
                
        # main loop
        while True:
            
            try:
                if not READY:
                    sleep(2)
                    raise ValueError

                printALLSET()
                if len(FIGURES) == 0:
                    print(f"{Style.BRIGHT}No shows scheduled{Style.RESET_ALL}. Add some figures to file {Fore.YELLOW}{Style.BRIGHT}{FIG_FILE}{R} to begin.")
                
                else:
                    figure = FIGURES[0]["Drones"]
                    destinos = {str(a["ID"]):[int(x) for x in a["POS"].split(',')] for a in figure}

                    figNombre = FIGURES[0]["Nombre"]
                    del FIGURES[0]
                    
                    print(f"{SHOW_START}{Fore.CYAN} Beginning figure {figNombre}.{R}")
                    register_event('Espectaculo',
                            f"Iniciando espectaculo con figura {figNombre}",
                            f"127.0.0.1")
                    resetDroneStatus()
                    dronesJOIN()

            except ValueError:
                pass
    except KeyboardInterrupt:
        raise KeyboardInterrupt
        

@app.route('/index')
def index():
    return "Hello, World!"

@app.route('/auth_drone', methods=['PUT'])
def auth_drone():
    global BOARD
    try:
        datas = request.get_json()
        client_ip = request.remote_addr
        
        idSent = datas['ID']
        tokenSent = datas['token']
        aliasSent = datas['alias']
        
        try:
            with open(DB_FILE, 'r') as file:
                datosDrones = json.load(file)
        except FileNotFoundError:
            datosDrones = dict()
        
        tokenDB = datosDrones[idSent]["token"]
        token_expiry_str = datosDrones[idSent]["expiry"]
        token_expiry = datetime.strptime(token_expiry_str, "%Y-%m-%d %H:%M:%S.%f")
        
        if datetime.now() > token_expiry:
            print(f"{NEW_CONNECTION}{Fore.MAGENTA} Drone {idSent}:{aliasSent} {Fore.RED}{Style.BRIGHT}Token expired.{R}")
            register_event('Authentication',
                            f"Authentication failed, token expired",
                            f"{client_ip}")
            
            raise Exception('Teken expired')
        else:
            hashed_token = base64.b64decode(tokenDB.encode('utf-8'))
        
            if not bcrypt.checkpw(tokenSent.encode('utf-8'), hashed_token):
                print(f"{NEW_CONNECTION}{Fore.MAGENTA} Drone {idSent} {Fore.RED}{Style.BRIGHT}failed to authenticate.{R}")
                register_event('Authentication',
                            f"Authentication from Drone {idSent} failed",
                            f"{client_ip}")
                
                raise Exception('Token is not valid')
            
            global PERFORMING
            
            symetric_key = Fernet.generate_key()
            print('Clave simetrica: ', symetric_key)
            save_symetric_key(idSent, symetric_key)

            if idSent in DRONES:
                
                if (BOARD[idSent]["status"] == 'X') or (BOARD[idSent]["status"] == 'N' and SHOW_IN_ACTION):
                    print(f"{NEW_CONNECTION}{Fore.MAGENTA} Drone {idSent}:{aliasSent} has reestablished connection (2).{R}")
                    register_event('Authentication',
                            f"Authentication from Drone {idSent} successful (2)",
                            f"{client_ip}")
                    
                    partition = DRONES[idSent]["partition"]
                    pos_recovery = BOARD[idSent]["POS"]
                    
                    response_data = {
                        'code': '2', 
                        'partition': partition,
                        'pos_recovery': str(pos_recovery),
                        'clave_simetrica': symetric_key.decode(),
                    }
                    response = {
                        'error' : False,
                        'message': 'Drone Added Successfully',
                        'data': response_data  
                    }
                    
                    PERFORMING[idSent] = {"status": False, "position": pos_recovery}
                    return jsonify(response), 200
                    
                else:
                    print(f"{NEW_CONNECTION}{Fore.MAGENTA} Drone {idSent}:{aliasSent} has reestablished connection (1).{R}")
                    partition = DRONES[idSent]["partition"]
                    
                    register_event('Authentication',
                            f"Authentication from Drone {idSent} reestablished",
                            f"127.0.0.1")
                    
                    response_data = {
                        'code': '1', 
                        'partition': partition,
                        'clave_simetrica': symetric_key.decode(),
                    }
                    response = {
                        'error' : False,
                        'message': 'Drone Added Successfully',
                        'data': response_data  
                    }

                    return jsonify(response), 200

            global DRONE_COUNT, ALIVE_DRONES
            
            BOARD[idSent] = {"status": 'N', "POS": [0, 0]}
            
            particion_asignada = (int(idSent) - 1)
            DRONES[idSent] = dict()
            DRONES[idSent]["partition"] = particion_asignada
            DRONES[idSent]["alias"] = aliasSent

            print(f"{NEW_CONNECTION}{Fore.MAGENTA} Drone {idSent}:{aliasSent} {Fore.GREEN}{Style.BRIGHT}authenticated (1).{R}")
            
            register_event('Authentication',
                            f"Authentication de  Drone {idSent} exitosa (1)",
                            f"{client_ip}")
            
            response_data = {
                'code': '1', 
                'partition': particion_asignada,
                'clave_simetrica': clave_simetrica.decode(),
            }
            response = {
                'error' : False,
                'message': 'Drone Added Successfully',
                'data': response_data  
            }

            consumerCoordinates = KafkaConsumer(
                bootstrap_servers=[argv[3]],
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='engine',
                value_deserializer=lambda x: decode_message(x, load_symetric_key(idSent))
            )

            consumerCoordinates.assign([TopicPartition(KTOPIC_MOVES, DRONES[idSent]["partition"])])
            
            #! Para leer mensajes que quedaron obsoletos
            try:
                consumerCoordinates.poll(timeout_ms=1000)
                consumerCoordinates.seek_to_end()
            except Exception:
                pass
            
            PERFORMING[idSent] = {"status": False, "position": None}
            
            thread = threading.Thread(target=handleDrone, args=(consumerCoordinates,str(idSent)))
            thread.start()

            DRONE_COUNT += 1
            
            # Return a JSON response with HTTP status code 201 (Created)
            return jsonify(response), 200
    except Exception as e:
        # Handle any exceptions that may occur during the process
        print(f'Error Ocurred: {e}')
        response_data = {
            'code': '666',
        }
        response = {
            'error' : True,
            'message': f'Error Ocurred: {e}',
            'data': response_data  
        }
        # Return a JSON response with HTTP status code 500 (Internal Server Error)
        return jsonify(response), 500

@app.route('/request_mapa', methods=['GET'])
def request_mapa():
    global BOARD, temperature, new_logs
    try:
        response = {
            "board": BOARD,
            "temperature": temperature,
            "logs": new_logs
        }
        new_logs = []
        return jsonify(response), 200
    except Exception as e:
        # Manejar excepciones
        return jsonify({'error': True, 'message': str(e)}), 500

try:
 
    if __name__ == "__main__":
        CORS(app, resources={r"*": {"origins": "*"}}, supports_credentials=True, methods=["GET", "POST", "PUT", "DELETE"])
        app.debug = False
        api_thread = threading.Thread(target=lambda:
            app.run(host=SERVER,
                    port=5002,
                    use_reloader=False,
                    ssl_context=(
                        CERT_FILE,
                        KEY_FILE)))
        api_thread.start()
        
        socket_thread = threading.Thread(target=startADEngine)
        socket_thread.start()
        
        api_thread.join()
        socket_thread.join()

except KeyboardInterrupt:
    print(f"\r{SHUTDOWN}")
    SHUTDOWN_SYSTEM = True
    display.stop()
    observer.stop()
    try:
        if server.fileno() != -1:
            server.shutdown(socket.SHUT_RDWR)
            server.close()
    except Exception as e:
        print(f"{Fore.RED}{Style.BRIGHT} Ha ocurrido un error inesperado: {e}{R}")
        exit()


    # liberar la memoria
    server.close()
    exit()

except Exception as e:
    #print(f"{Fore.RED}{Style.BRIGHT} Ha ocurrido un error inesperado: {e}{R}")
    pass