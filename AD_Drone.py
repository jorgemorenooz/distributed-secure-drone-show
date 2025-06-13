from cryptography.fernet import Fernet
import socket
import sys
import json
from os import remove
import threading
from time import sleep, time
from random import randrange
from json import dumps,loads
from os import path, makedirs
#from confluent_kafka import Consumer, Producer, TopicPartition
from kafka import KafkaConsumer, KafkaProducer, TopicPartition
from colorama import init as colorama_init
from colorama import Fore, Style
from typing import Optional
from AD_Display import Display
import ssl
import requests
import urllib3
from getpass import getpass
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

colorama_init()

FORMAT = 'utf-8'
RETREAT = False

R = f"{Style.RESET_ALL}"
SHUTDOWN = f"{Fore.RED}{Style.BRIGHT}[SHUTDOWN]{R}"
ERROR = f"{Fore.RED}{Style.BRIGHT}[ERROR]{R}"
NEW = f"{Fore.GREEN}{Style.BRIGHT}[NEW]{R}"
WEATHER_ALERT = f"{Fore.MAGENTA}{Style.BRIGHT}[WEATHER_ALERT]{R}"
SUCCESS = f"{Fore.GREEN}{Style.BRIGHT}[SUCCESS]{R}"
MISSING = f"{Style.BRIGHT}{Fore.RED}[MISSING]{R}"

KTOPIC_MOVES = 'droneMoves'
KTOPIC_ORDERS = 'droneOrders'
KTOPIC_BOARDS = 'droneBoards'
PARTITION_NUMBER = 0

SHUTDOWN_SYSTEM = False
RETRY_ENGINE = False
MAP = False
PERFORMING = False

BOARD = dict() # {ID1: {"POS":[1,2], "status":status}, ID2:{}...}
ENGINE_SECS = 3.0 # segundos antes de dar al engine por muerto
MOVE_DELAY = 2 # cada cuánto hacer un movimiento

POSITION = [0,0]
DESTINO = list()


def retryEngine(doiprint):
    global SHUTDOWN_SYSTEM, RETRY_ENGINE, RETREAT

    if doiprint:
        print(f"{Fore.MAGENTA}[INACTIVE]{Style.DIM} Checking connection to {Style.NORMAL}{Fore.YELLOW}AD_Engine{Style.DIM}{Fore.MAGENTA} in background...{R}\r")
    i = 0
    while RETRY_ENGINE:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(ENGINE_ADDR)
            RETRY_ENGINE = False
            s.close()
            return
        except ConnectionRefusedError:
            i += 1
            if i > 5:
                if POSITION != [0,0]:
                    print(f"{MISSING}{Fore.RED}{Style.BRIGHT} AD_Engine considered dead. Returning to base and pinging...{R}")
                    RETREAT = True
                else:
                    print(f"{MISSING}{Fore.RED}{Style.BRIGHT} AD_Engine considered dead. Pinging...{R}\r")
                
                while True:
                    try:
                        s.connect(ENGINE_ADDR)
                        RETRY_ENGINE = False
                        s.close()
                        return
                    except ConnectionRefusedError:
                        i += 1
                        if i > 10:
                            print(f"{MISSING}{Fore.RED}{Style.BRIGHT} AD_Engine unreachable. Shutting down for energy usage.{R}")
                            SHUTDOWN_SYSTEM = True
                            return
                        sleep(1)
                    except OSError:
                        pass
            sleep(1)
        except OSError:
            # probably s.connect freaked out during ctrl+c
            pass

def msgWrap(msg:str):
  
    #print(f"wrapping msg {msg}")
    msg = msg.encode(FORMAT)
    lrc = msg[0]
    for c in msg[1:]:
        lrc = lrc ^ c
    return b'\x02' + msg + b'\x03' + str(lrc).encode(FORMAT)
 
def msgUnwrap(msg) -> Optional[str]:
 
    #print(f"unwrapping msg {msg}")
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

def saveToken(token):

    filepath = path.join('./login_para_Drones', f'{DRONE_NAME[0]}.{DRONE_NAME[1]}.txt')
    
    if not path.exists('./login_para_Drones'):
        makedirs('./login_para_Drones')

    with open(filepath, 'w') as file:
        file.write(str(token))


#!###### CLAVE SIMETRICA ############

def guardar_clave_simetrica(id_dron, clave):
    
    filepath = path.join('./claves_Drone', f"{id_dron}.txt")
    
    if not path.exists('./claves_Drone'):
        makedirs('./claves_Drone')
        
    with open(filepath, 'w') as file:
        file.write(str(clave))
        
    sleep(1)

def cifrar_mensaje(mensaje, clave_simetrica):
    
    try:
        fernet = Fernet(clave_simetrica)
        mensaje_cifrado = fernet.encrypt(mensaje.encode())
    except Exception:
        clave_simetrica = Fernet.generate_key()
        fernet = Fernet(clave_simetrica)
        mensaje_cifrado = fernet.encrypt(mensaje.encode())
    return mensaje_cifrado.decode(FORMAT)

def descifrar_mensaje(mensaje_cifrado, clave_simetrica):
    
    try:
        fernet = Fernet(clave_simetrica)
    except Exception:
        clave_simetrica = Fernet.generate_key()
        fernet = Fernet(clave_simetrica)
    
    try:
        mensaje_a_cifrar = mensaje_cifrado.decode('utf-8')
        mensaje_descifrado = fernet.decrypt(mensaje_a_cifrar)  # Decodificar los bytes a una cadena
        
        return [json.loads(mensaje_descifrado), True]
    
    except Exception as e:        
        return [None, False]

def load_clave_simetrica(id_dron):
    
    filepath = path.join('./claves_Drone', f"{id_dron}.txt")
    
    try:
        with open(filepath, 'r') as file:
            return file.read()
    except Exception as e:
        return Fernet.generate_key() # otra clave random y fallara el cifrado

#!###################################

################################
#          AUDITORIA           #
################################

def registrar_auditoria(accion, descripcion, ip):
    filepath = path.join('./log', f"events.log")
    
    if not path.exists('./log'):
        makedirs('./log')

    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    evento = f"{fecha} - IP: {ip}, Acción: {accion}, Descripción: {descripcion}\n"
    
    with open(filepath, 'a') as archivo:
        archivo.write(evento)

################################
#            API               #
################################

def registerDroneAPI():
    try:
        # Preparar los datos para la solicitud
        registration_data = {"ID": DRONE_NAME[0], "Alias": DRONE_NAME[1]}

        registry_url = f"https://{REGISTRY_API_ADDR}/add_drone"

        response = requests.post(registry_url, json=registration_data, verify=False)

        # Verificar la respuesta y guardar el token
        if response.status_code == 200:
            token = response.json()['data']['token']
            print(f"{Fore.GREEN}Token: {token}{R}")
            saveToken(token)
            print(f"{SUCCESS} Registration successful.{R}")
        else:
            print(f"{ERROR} Registration failed with status code: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"{ERROR} An error occurred: {e}")

    except Exception as e:
        print(f"{ERROR} An unexpected exception occurred: {e}")

def authToEngineAPI():
    global RETRY_ENGINE, PARTITION_NUMBER, POSITION, ENGINE_API_ADDR
    try:
        # Preparar los datos para la solicitud
        token = getToken()
        registration_data = {"ID": DRONE_NAME[0],"alias":DRONE_NAME[1], "token": token}
        registry_url = f"https://{ENGINE_API_ADDR}/auth_drone"

        response = requests.put(registry_url, json=registration_data, verify=False)

        # Verificar la respuesta y guardar el token
        if response.status_code == 200:
            code = response.json()['data']['code']
            if code == '1':
                PARTITION_NUMBER = int(response.json()['data']['partition'])
                clave_simetrica = response.json()['data']['clave_simetrica']
                print(f"{Fore.BLUE}Clave simetrica: {clave_simetrica}{R}")
                guardar_clave_simetrica(DRONE_NAME[0],clave_simetrica)
                #print("Mi particion es: " + str(PARTITION_NUMBER))
                
                print(f"{Fore.GREEN}{Style.BRIGHT}Authentication to Engine successful (1).{R}")

                return True
            elif code == '2':
                PARTITION_NUMBER = int(response.json()['data']['partition'])
                clave_simetrica = response.json()['data']['clave_simetrica']
                pos_string = response.json()['data']['pos_recovery']
                pos_list = json.loads(pos_string)
                POSITION = [int(pos_list[0]), int(pos_list[1])]
                
                print(f"{Fore.BLUE}Clave simetrica: {clave_simetrica}{R}")
                guardar_clave_simetrica(DRONE_NAME[0],clave_simetrica)
                
                print(f"{Fore.GREEN}{Style.BRIGHT}Authentication to Engine successful (2).{R}")
                print(f"{Fore.BLUE}{Style.BRIGHT}Parece que me he desconectado en la posicion {POSITION}.{R}")
                
                reconex = [-2,-2]
                data = {'POS' : reconex}
                clave_simetrica = load_clave_simetrica(DRONE_NAME[0])
                data_cifrada = cifrar_mensaje(json.dumps(data), clave_simetrica)
                sleep(1.5)
                
                movesProducer.send(KTOPIC_MOVES, value=data_cifrada, partition=PARTITION_NUMBER)
                movesProducer.flush()
                
                return True
            else:
                print(f"{Fore.RED}{Style.BRIGHT}Authentication failed.{R}")
                return False
        else:
            print(f"{ERROR} Registration failed with status code: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"{ERROR} An error occurred: {e}")
        return False

    except Exception as e:
        print(f"{ERROR} An unexpected exception occurred: {e}")
        return False

################################
#            AUTH              #
################################

def getToken():
    filepath = path.join('./login_para_Drones', f"{DRONE_NAME[0]}.{DRONE_NAME[1]}.txt")
    try:
        with open(filepath, 'r') as file:
            line = file.readline()
    except FileNotFoundError:
        line = ''
    except Exception as e:
        print(f"An unexpected exception occured during a reading for token -> {str(e)}")
    return str(line)
  
def registerDrone():
    context = ssl._create_unverified_context()

    try:
        with socket.create_connection(REGISTRY_ADDR) as sock:
            with context.wrap_socket(sock, server_hostname=REGISTRY_ADDR[0]) as ssock:
                print(f"{Fore.MAGENTA}Drone {Style.BRIGHT}{DRONE_NAME[0]}:{DRONE_NAME[1]}{Style.RESET_ALL} registering in {Fore.YELLOW}{Style.BRIGHT}{sys.argv[3]}{Style.RESET_ALL}") 
                
                registration_data = {"ID": DRONE_NAME[0], "Alias": DRONE_NAME[1]}
                ssock.sendall(msgWrap(json.dumps(registration_data)))
                messages = msgUnwrap(ssock.recv(2048))

                if messages:
                    saveToken(messages.split(' ')[1])
                    print(f"{Fore.GREEN}Token: {messages.split(' ')[1]}{R}")
                    print(f"{Fore.GREEN}{Style.BRIGHT}Registration successful.{Style.RESET_ALL}")

    except ConnectionRefusedError as c:
        print(f"{Fore.RED}{Style.BRIGHT}Failed to register because Registry is unreachable. Reattempting...{Style.RESET_ALL}")
        sleep(1)
        registerDrone()
    except Exception as e:
        print(f"{Fore.RED}{Style.BRIGHT}An unexpected exception occurred during registration -> {str(e)}{Style.RESET_ALL}")

def authToEngine():

    global RETRY_ENGINE, PARTITION_NUMBER, POSITION
    
    while not SHUTDOWN_SYSTEM:
        context = ssl._create_unverified_context()
        try:
            token = getToken()
            if token == '':
                print(f"{ERROR} {Fore.RED}Unable to find credentials. Registration needed.{R}")
                return False
            
            with socket.create_connection(ENGINE_ADDR) as sock:
                with context.wrap_socket(sock, server_hostname=ENGINE_ADDR[0]) as client_drone:
                    print(f"{Fore.MAGENTA}Drone {Style.BRIGHT}{DRONE_NAME[0]}:{DRONE_NAME[1]}{R} authenticating in {Fore.YELLOW}{Style.BRIGHT}{sys.argv[1]}{R}")
                    registration_data = {"ID": DRONE_NAME[0],"alias":DRONE_NAME[1], "token": token}
                    client_drone.sendall(msgWrap(json.dumps(registration_data)))
                    messages_raw = msgUnwrap(client_drone.recv(2048))

                    if messages_raw:
                        messages = messages_raw.split(' ')

                        if messages == 'wait':
                            print(f"{Fore.RED}{Style.BRIGHT}There are no slots left. Try again later.{R}") 
                            return False

                        if messages[0] == '1':
                            PARTITION_NUMBER = int(messages[1])
                            clave_simetrica = messages[2]

                            print(f"{Fore.BLUE}Clave simetrica: {clave_simetrica}{R}")
                            guardar_clave_simetrica(DRONE_NAME[0],clave_simetrica)
                            #print("Mi particion es: " + str(PARTITION_NUMBER))
                            
                            print(f"{Fore.GREEN}{Style.BRIGHT}Authentication to Engine successful (1).{R}")

                            return True
                        elif messages[0] == '2':
                            PARTITION_NUMBER = int(messages[1])
                            pos_string = int(messages[2])
                            clave_simetrica = messages[3]
                            POSITION = [int(pos_string[0]), int(pos_string[1])]
                            
                            print(f"{Fore.BLUE}Clave simetrica: {clave_simetrica}{R}")
                            guardar_clave_simetrica(DRONE_NAME[0],clave_simetrica)
                            
                            print(f"{Fore.GREEN}{Style.BRIGHT}Authentication to Engine successful (2).{R}")
                            print(f"{Fore.BLUE}{Style.BRIGHT}Parece que me he desconectado en la posicion {POSITION}.{R}")
                            
                            reconex = [-2,-2]
                            data = {'POS' : reconex}
                            clave_simetrica = load_clave_simetrica(DRONE_NAME[0])
                            data_cifrada = cifrar_mensaje(json.dumps(data), clave_simetrica)
                            sleep(1.5)
                            
                            movesProducer.send(KTOPIC_MOVES, value=data_cifrada, partition=PARTITION_NUMBER)
                            movesProducer.flush()
                            
                            return True
                        else:
                            print(f"{Fore.RED}{Style.BRIGHT}Authentication failed.{R}")
                            return False

        except (TimeoutError, ConnectionRefusedError, ConnectionResetError) as e:
            client_drone.close()
            if not RETRY_ENGINE:
                RETRY_ENGINE = True
                retryEngine(True)
        
        except Exception as e:
            print(f"{Fore.RED}An unexpected exception occured during authentication -> {str(e)}{R}")
            client_drone.close()
            return False

def move():
    global RETREAT, POSITION, PERFORMING
    PERFORMING = True
    arrived = False
    
    print("Moviendome desde ", POSITION, " hasta ", DESTINO)
    while not SHUTDOWN_SYSTEM:
        
        if arrived:
            break
        
        if POSITION == DESTINO:
            if not arrived: #Si no habia llegado
                print(f"{Fore.CYAN}{Style.BRIGHT}Movement complete. Awaiting new orders.{R}")
                arrived = True
                
                llegada = [-1,-1]
                data = {'POS' : llegada}
                clave_simetrica = load_clave_simetrica(DRONE_NAME[0])
                data_cifrada = cifrar_mensaje(json.dumps(data), clave_simetrica)
                
                
                movesProducer.send(KTOPIC_MOVES, value=data_cifrada, partition=PARTITION_NUMBER)
                movesProducer.flush()
                PERFORMING = False
            sleep(1)
            continue
        
        arrived = False
        #print(f"current: {POSITION} final: {DESTINO}")
        n = randrange(2)
        #print(f"n is {n}")
        if POSITION[0] < DESTINO[0]:
            POSITION[0] += 1
            if n==0 and POSITION[1] < DESTINO[1]:
                POSITION[1] += 1
                print(f"Down-Right to {POSITION}")
            elif n==1 and POSITION[1] > DESTINO[1]:
                POSITION[1] -= 1
                print(f"Down-Left to {POSITION}")
            else:
                print(f"Right to {POSITION}")
            
        elif POSITION[0] > DESTINO[0]:
            POSITION[0] -= 1
            if n==0 and POSITION[1] < DESTINO[1]:
                POSITION[1] += 1
                print(f"Up-Right to {POSITION}")
            elif n==1 and POSITION[1] > DESTINO[1]:
                POSITION[1] -= 1
                print(f"Up-Left to {POSITION}")
            else:
                print(f"Up to {POSITION}")
    
        elif POSITION[1] < DESTINO[1]:
            POSITION[1] += 1
            print(f"Right to {POSITION}")
        
        elif POSITION[1] > DESTINO[1]:
            POSITION[1] -= 1
            print(f"Left to {POSITION}")
        

        data = {'POS' : POSITION}
        clave_simetrica = load_clave_simetrica(DRONE_NAME[0])
        data_cifrada = cifrar_mensaje(json.dumps(data), clave_simetrica)
        
        
        movesProducer.send(KTOPIC_MOVES, value=data_cifrada, partition=PARTITION_NUMBER)
        movesProducer.flush()
        sleep(MOVE_DELAY)
    
    PERFORMING = False
    RETREAT = False

def realizar_checkeo(producerVerification):
    
    try:
        data = {"POS": [-3, -3]}
        clave_simetrica = load_clave_simetrica(DRONE_NAME[0])
        data_cifrada = cifrar_mensaje(json.dumps(data), clave_simetrica)
        
        
        producerVerification.send(KTOPIC_MOVES, value=data_cifrada, partition=PARTITION_NUMBER)
        producerVerification.flush()
    except Exception as e:
        print(f"{ERROR}Error verificando el estado de Engine: {e}{R}")

def salirDelPrograma():
    getpass('')

################################
#            SHOW              #
################################

def perform(option):
    global RETRY_ENGINE, DESTINO
    ultimo_checkeo = time()
    checkear_cada = 10
    engine_vivo = True
    tiempo_margen = 5
    primera_vez = True
    
    auth = False
    
    if option == '-raea' or option == '-rsea' or option == '-ea':
        auth = authToEngineAPI()
    else:
        auth = authToEngine()
        
    if auth:
        #Consumir del topic "drone_orders" la pF
        consumerOrders = KafkaConsumer(
            bootstrap_servers=[sys.argv[2]],
            group_id='drones',
            auto_offset_reset='latest',
            value_deserializer=lambda x: descifrar_mensaje(x, load_clave_simetrica(DRONE_NAME[0]))
        )

    
        consumerOrders.assign([TopicPartition(KTOPIC_ORDERS, PARTITION_NUMBER)])
        #! Para leer mensajes que quedaron obsoletos
        consumerOrders.poll(timeout_ms=1000)
        
        producerVerification = KafkaProducer(bootstrap_servers=[sys.argv[2]],
                                       value_serializer=lambda v: json.dumps(v).encode('utf-8'))
        
        # lee ordenes
        while not SHUTDOWN_SYSTEM:
            current_time = time()
            
            if current_time - ultimo_checkeo > checkear_cada:
                realizar_checkeo(producerVerification)
                ultimo_checkeo = current_time
                engine_vivo = False  # el Engine está caído hasta que se confirme lo contrario
            
            try:
                # Comprobar si hay mensajes en el topic de Kafka
                try:
                    consumerRecords = consumerOrders.poll(timeout_ms=1000)
                except Exception:
                    continue
                
                if not consumerRecords: # No hay mensaje nuevo
                    if not engine_vivo and (current_time - ultimo_checkeo > tiempo_margen) and primera_vez:
                        print(f"{MISSING}{Fore.RED} El Engine está caído. Volviendo a la posición inicial.{R}")
                        DESTINO = [0, 0]
                        primera_vez = False
                        movement = threading.Thread(target=move)
                        movement.start()
                
                    if not engine_vivo and not primera_vez:
                        
                        try:
                            registerDroneAPI()
                            print("authToEngine")
                            if(authToEngineAPI()):
                                engine_vivo = True
                                primera_vez = True
                                sleep(3)
                                continue
                        except Exception:
                            continue
                    
                    continue
                
                for record in consumerRecords.values():
                    for message in record:
                        exito = message.value[1]
                        if exito:
                            engine_vivo = True
                            primera_vez = True
                            pos_string = message.value[0]["POS"]
                            
                            if not pos_string == "-3 -3":
                                DESTINO = [int(x) for x in pos_string.split()]
                                print(f"{NEW}{Fore.GREEN} Orders from the Engine: move to {Style.BRIGHT}{Fore.WHITE}{DESTINO}{R}")
                                movement = threading.Thread(target=move)
                                movement.start()
                        else:
                            partition = message.partition  # Obtener la partición del mensaje
                            print(f"Engine in partition {partition}, I do not understand you, key {load_clave_simetrica(DRONE_NAME[0])}")
                                    
                            registrar_auditoria('Error decrypting message',
                                            f"Engine, I do not understand you",
                                            'localhost')
                            
                            registerDroneAPI()
                            if(authToEngineAPI()):
                                engine_vivo = True
                                primera_vez = True
                                sleep(1)
                    
            except Exception as e:
                print(f"An unexpected error occured while listening for new orders -> {str(e)}")
                pass

def readBoards():
    global RETRY_ENGINE, BOARD
    checked = False
    drone_id = DRONE_NAME[0]
    
    consumerBoard = KafkaConsumer(
        bootstrap_servers=[sys.argv[2]],
        group_id=f'drone_group_{drone_id}',
        auto_offset_reset='latest',
        value_deserializer=lambda x: descifrar_mensaje(x, load_clave_simetrica(DRONE_NAME[0]))
    )
    # Suscribirse al topic completo
    consumerBoard.subscribe([KTOPIC_BOARDS])
    
    #! Para leer mensajes que quedaron obsoletos
    try:
        consumerBoard.poll(timeout_ms=1000)
        consumerBoard.seek_to_end()
    except Exception:
        pass
    
    while not SHUTDOWN_SYSTEM:
        
        try:
            records = consumerBoard.poll(timeout_ms=int(ENGINE_SECS * 1000))
            
            if records:
                for topic_partition, messages in records.items():
                    for message in messages:
                        exito = message.value[1]
                        if exito:
                            try:
                                # Asumiendo que message.value ya es una cadena JSON debido al value_deserializer
                                board_data = message.value[0]
                                BOARD = board_data
                                display.update(BOARD)
                            except json.JSONDecodeError as e:
                                print(f"Error decoding JSON: {e}")
                            except Exception as e:
                                print(f"Unexpected error: {e}")
                        else:
                            print(f"Engine, I do not understand you")
            
                            registrar_auditoria('Error decrypting message',
                                            f"Engine, I do not understand you",
                                            'localhost')
        except Exception as e:
            print(f"{ERROR} Error al leer el BOARD: {e}")

##########   MAIN #########################
# Parse parameters from command line
#  argv[1] = IP:port of AD_Engine
#  argv[2] = IP:port of kafka broker
#  argv[3] = IP:port of AD_Registry
#  argv[4] = -r / -e / -re
#  argv[5] = <ID>:<Alias>
if __name__ == "__main__":
    try:
        if len(sys.argv) >= 5:
        
            engine = sys.argv[1].split(':', 2)
            ENGINE_ADDR = (engine[0], int(engine[1]))
            ENGINE_API_ADDR = f"{engine[0]}:5002"
            broker = sys.argv[2].split(':', 2)
            BROKER_ADDR = (broker[0], int(broker[1]))
            registry = sys.argv[3].split(':', 2)
            REGISTRY_ADDR = (registry[0], int(registry[1]))
            REGISTRY_API_ADDR = f'{registry[0]}:5001'
            
            movesProducer = None
            while not movesProducer:
                try:
                    movesProducer = KafkaProducer(
                        bootstrap_servers=[sys.argv[2]],
                        value_serializer=lambda x: json.dumps(x).encode('utf-8')
                    )
                except Exception as e:
                    print(f"An unexpected error occured while conecting to broker {BROKER_ADDR} -> {str(e)}")
                    break
                    

            if len(sys.argv) >= 6:
                name = sys.argv[5].split(':', 2)
                DRONE_NAME = (name[0], name[1])

                option = str(sys.argv[4])

                if(option == '-ra'):
                    registerDroneAPI()
                    
                elif(option == '-rs'):
                    registerDrone()
                    
                elif(option == '-e'):
                    performThread = threading.Thread(target=perform, args=(option,))
                    performThread.start()
                
                elif(option == '-ea'):
                    performThread = threading.Thread(target=perform, args=(option,))
                    performThread.start()

                elif option=='-rses':
                    registerDrone()
                    performThread = threading.Thread(target=perform, args=(option,))
                    performThread.start()
                    
                elif option=='-raes':
                    registerDroneAPI()
                    performThread = threading.Thread(target=perform, args=(option,))
                    performThread.start()
                    
                elif option=='-raea':
                    registerDroneAPI()
                    performThread = threading.Thread(target=perform, args=(option,))
                    performThread.start()
                    
                elif option=='-rsea':
                    registerDrone()
                    performThread = threading.Thread(target=perform, args=(option,))
                    performThread.start()
                
                if(name[0] == '1'):
                    MAP = True
                    display = Display(id=name[0])
                    display.start()
                    boardsThread = threading.Thread(target=readBoards)
                    boardsThread.start()
                    

            else:
                name = sys.argv[4].split(':', 2)
                DRONE_NAME = (name[0], name[1])
                
                opt = input(f"{Style.BRIGHT}How do you want to proceed{R} \n 1. Register \n 2. Join the show\n 3. Dhut down drone \n Select your option (1-3):")

                if opt == '1':
                    registerDroneAPI()

                elif opt == '2':
                    sn = input(f"{Style.BRIGHT}Do you wish to show the map?{Style.DIM}(s/n):{R}").lower()
                    
                    if sn =='s':
                        MAP = True
                        display = Display(id=name[0])
                        display.start()
                        boardsThread = threading.Thread(target=readBoards)
                        boardsThread.start()

                    performThread = threading.Thread(target=perform)
                    performThread.start()
                    
            salirDelPrograma()
            raise KeyboardInterrupt
        else:
            print("ARGUMENT MISSING. AD_Drone receives arguments: <AD_Engine IP:port> <broker IP:port> <AD_Registry IP:port> <options> <ID:Alias>")
    except KeyboardInterrupt:
        SHUTDOWN_SYSTEM = True
        print(f"\r{SHUTDOWN}")
        try:
            display.stop()
        except:
            pass
        
        exit()
