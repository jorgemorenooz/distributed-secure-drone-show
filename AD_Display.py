from contextlib import redirect_stdout
import pygame
with redirect_stdout(None):
    from pygame import init, display, draw, quit, QUIT
    from pygame import event as pyevent
    from pygame.time import Clock
    from pygame.font import SysFont
from random import randrange
import threading

class Colors:
    NEGRO       = ( 20,  20,  20)
    BLANCO      = (255, 255, 255)
    ROJO        = (224,  52,  18)
    VERDE       = ( 59, 224,  18)
    ROJO_OSCURO = (125,  35,  35)
    AMARILLO    = (229, 213,  10)

class Display:

    SIZE_MULTIPLIER = 2
    SELF_ID = None 
    BOARD = {}
    FILS = 20
    COLS = 20
    begun = False
    F_QUIT = False

    def __init__(self, size=1, id=None):
        
        Display.SIZE_MULTIPLIER = size
        Display.SELF_ID = id

    def start(self):

        if Display.SELF_ID == None:

            screen = threading.Thread(target=displayBoardENGINE)
        else:
            screen = threading.Thread(target=displayBoardDRONE)
        
        screen.start()

    def update(self, board):
        if Display.F_QUIT:
            return False
        if not isinstance(board, dict):
            print("Error: El BOARD is not a dictionary.")
            return False
        
        for dron_id, dron_data in board.items():
            if "POS" not in dron_data or "status" not in dron_data:
                print(f"Error: Data missing from Drone {dron_id}.")
                return False
        Display.BOARD = board
        
    def stop(self):
        Display.F_QUIT = True

def displayBoardENGINE():
    
    MARGEN  =  1 * Display.SIZE_MULTIPLIER  		    
    TAM     = 40 * Display.SIZE_MULTIPLIER 		    
    PADDING = 6*MARGEN * Display.SIZE_MULTIPLIER

    FILS = Display.FILS
    COLS = Display.COLS

    init()

    reloj=Clock()

    anchoVentana=COLS*(TAM+MARGEN)+2*PADDING
    altoVentana= FILS*(TAM+MARGEN)+2*PADDING

    dimension=[anchoVentana,altoVentana]
    screen=display.set_mode(dimension) 
    display.set_caption(f"Art with Drones · Engine's POV")

    myFont = SysFont('Noto Mono', int(TAM/3)+4, bold=True)

    
    estrellas = list() # [ (x,y), (x,y)... ]
    for i in range(Display.SIZE_MULTIPLIER * 15):
        estrellas.append((randrange(altoVentana), randrange(anchoVentana)))

    # game loop
    while not Display.F_QUIT:

        for event in pyevent.get():

            if event.type==QUIT:               
                Display.F_QUIT = True

        try:
            backgroundImage = pygame.image.load('./img/Disney_Pictures.jpeg')
        except Exception:
            backgroundImage = pygame.Surface((anchoVentana, altoVentana))
            backgroundImage.fill((30, 30, 30))

        backgroundImage = pygame.transform.scale(backgroundImage, (anchoVentana, altoVentana))
        screen.blit(backgroundImage, (0, 0))

        for estrella in estrellas:
            draw.circle(screen, (180, 180, 180), (estrella[0], estrella[1]), randrange(2))

        for dron_id, dron_data in dict(Display.BOARD).items():
            if 'POS' in dron_data and 'status' in dron_data:
                col = dron_data["POS"][0]
                fil = dron_data["POS"][1]
                status = dron_data["status"]
                
                try:
                    droneImg = pygame.image.load('./img/drone-yellow.png')
                    droneImg = pygame.transform.scale(droneImg, (TAM, TAM))
                except Exception:
                    droneImg = pygame.Surface((TAM, TAM), pygame.SRCALPHA)
                    center = (TAM // 2, TAM // 2)
                    pygame.draw.circle(droneImg, (255, 255, 0), center, TAM // 6)  # small yellow dot

                
                # Draw the drone on its current position
                screen.blit(droneImg, ((TAM + MARGEN) * col + PADDING, (TAM + MARGEN) * fil + PADDING))
                
                text_color = Colors.BLANCO if status == 'N' else (Colors.VERDE if status == 'Y' else Colors.ROJO)
                # Drone ID over the picture
                screen.blit(myFont.render(str(dron_id), True, text_color),
                            ((TAM + MARGEN) * col + PADDING + TAM / 4 - TAM / 8, (TAM + MARGEN) * fil + PADDING + TAM / 4 - TAM / 8))
            else:
                print(f"Error: Data missing from Drone {dron_id}.")


        # update screen
        display.flip()        
        reloj.tick(20)

    quit()

def displayBoardDRONE():
    
    MARGEN  =  1 * Display.SIZE_MULTIPLIER  		    
    TAM     = 40 * Display.SIZE_MULTIPLIER 		    
    PADDING = 6*MARGEN * Display.SIZE_MULTIPLIER

    FILS = Display.FILS
    COLS = Display.COLS

    init()

    reloj=Clock()

    anchoVentana=COLS*(TAM+MARGEN)+2*PADDING
    altoVentana= FILS*(TAM+MARGEN)+2*PADDING

    dimension=[anchoVentana,altoVentana]
    screen=display.set_mode(dimension) 
    display.set_caption(f"Art with Drones · Drone {Display.SELF_ID}'s POV")

    myFont = SysFont('Noto Mono', int(TAM/3)+4, bold=True)

    estrellas = list() # [ (x,y), (x,y)... ]
    for i in range(Display.SIZE_MULTIPLIER * 15):
        estrellas.append((randrange(altoVentana), randrange(anchoVentana)))


    # game loop
    while not Display.F_QUIT:

        for event in pyevent.get():

            if event.type==QUIT:               
                Display.F_QUIT = True

        try:
            backgroundImage = pygame.image.load('./img/Disney_Pictures.jpeg')
        except Exception:
            backgroundImage = pygame.Surface((anchoVentana, altoVentana))
            backgroundImage.fill((30, 30, 30))
            
        backgroundImage = pygame.transform.scale(backgroundImage, (anchoVentana, altoVentana))
        screen.blit(backgroundImage, (0, 0))

        for estrella in estrellas:
            draw.circle(screen, (180, 180, 180), (estrella[0], estrella[1]), randrange(2))

        for dron in dict(Display.BOARD):
            #print(f"fasd :{Display.BOARD[dron]}")
            id = dron
            col = Display.BOARD[dron]["POS"][0]
            fil = Display.BOARD[dron]["POS"][1]
            status = Display.BOARD[dron]["status"]

            try:
                droneImg = pygame.image.load('./img/drone-yellow.png')
                droneImg = pygame.transform.scale(droneImg, (TAM, TAM))
            except Exception:
                droneImg = pygame.Surface((TAM, TAM), pygame.SRCALPHA)
                center = (TAM // 2, TAM // 2)
                pygame.draw.circle(droneImg, (255, 255, 0), center, TAM // 6)  # small yellow dot
            
            # Draw the drone on its current position
            screen.blit(droneImg, ((TAM + MARGEN) * col + PADDING, (TAM + MARGEN) * fil + PADDING))
            
            
            text_color = Colors.BLANCO if status == 'N' else (Colors.VERDE if status == 'Y' else Colors.ROJO)
            # Drone ID over the picture
            screen.blit(myFont.render(str(id), True, text_color),
                        ((TAM + MARGEN) * col + PADDING + TAM / 4 - TAM / 8, (TAM + MARGEN) * fil + PADDING + TAM / 4 - TAM / 8))

        display.flip()
        reloj.tick(40)

    quit()
