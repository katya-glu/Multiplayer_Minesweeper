from plot_high_score_class import HighScore
from tkinter import *
from tkinter import messagebox
from Board import Board
import random
import pygame
import time
import numpy as np
import threading
from kafka import KafkaConsumer
from kafka import KafkaProducer
import json
pygame.init()


# board size constants
num_of_tiles_x_small_board = 8
num_of_tiles_y_small_board = 8
num_of_mines_small_board = 4

num_of_tiles_x_medium_board = 13
num_of_tiles_y_medium_board = 15
num_of_mines_medium_board = 40

num_of_tiles_x_large_board = 30
num_of_tiles_y_large_board = 16
num_of_mines_large_board = 99

# constants
prod_id_max_val = (2 ** 32) - 1

# global vars
action_queue = []
run = True
producer_id = 0

def get_board_size(size_str):
    # function gets size_str from open_opening_window func in game_class file
    board_shape_dict = {
        "Small":  (num_of_tiles_x_small_board, num_of_tiles_y_small_board, num_of_mines_small_board),
        "Medium": (num_of_tiles_x_medium_board, num_of_tiles_y_medium_board, num_of_mines_medium_board),
        "Large":  (num_of_tiles_x_large_board, num_of_tiles_y_large_board, num_of_mines_large_board)
                       }

    for key in board_shape_dict:
        if size_str == key:
            return board_shape_dict[key]

def open_opening_window():   # TODO: add comments
    # Create an instance of the HighScore class
    high_scores = HighScore(True, 10, [10, 5], [True, False], "high_scores.pkl")

    opening_window = Tk()
    opening_window.title("Opening window")

    MODES = [("Small", "Small"), ("Medium","Medium"), ("Large", "Large")]
    board_size = StringVar()
    board_size.set("Small")

    for mode, size in MODES:
        Radiobutton(opening_window, text=mode, variable=board_size, value=size).pack()

    def start_new_game():
        board_size_str = board_size.get()
        size_index = 0
        for mode in MODES:
            if board_size_str == mode[0]:
                size_index = MODES.index(mode)

        board_size_and_num_of_mines = get_board_size(board_size_str)
        num_of_tiles_x = board_size_and_num_of_mines[0]
        num_of_tiles_y = board_size_and_num_of_mines[1]
        num_of_mines = board_size_and_num_of_mines[2]
        opening_window.destroy()
        main(size_index, num_of_tiles_x, num_of_tiles_y, num_of_mines)
        open_opening_window()

    def open_high_scores():
        if not high_scores.is_window_open():
            high_scores.load_scores_from_file()
            high_scores.display_high_scores_window()

    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            opening_window.destroy()

    start_game_button = Button(opening_window, text="Start game", command=start_new_game)
    start_game_button.pack()

    high_scores_button = Button(opening_window, text="High scores", command=open_high_scores)
    high_scores_button.pack()

    opening_window.protocol("WM_DELETE_WINDOW", on_closing)
    opening_window.mainloop()

def add_high_score(game_board, score, size_index):
    high_scores = HighScore(False, 10, [10, 5], [True, False], "high_scores.pkl")
    high_scores.add_new_high_score(score, size_index)
    game_board.add_score = False

def kafka_consumer(topic_name):
    TOPIC_NAME = topic_name

    consumer = KafkaConsumer(TOPIC_NAME, value_deserializer=lambda data: json.loads(data.decode('utf-8')))
    global run

    for message in consumer:
        # message.value contains dict with pressed tile data or 'quit' command
        # checking run flag to close only local consumer
        # if key not in dict, dict.get(key) will return None. flag will be used to continue gameplay
        quit_val = message.value.get('quit')
        if not run and quit_val:
            #print('killing kafka consumer')
            break

        # if quit_val == None, game continues for user
        if not quit_val:
            pressed_tile_data_dict = message.value
            producer_id_from_kafka = message.value['producer_id']
            global producer_id
            if producer_id_from_kafka == producer_id:
                from_local_producer = True
            else:
                from_local_producer = False
            #print("producer_id_from_kafka: ", producer_id_from_kafka)
            #print("from_local_producer: ", from_local_producer)

            action_queue.append([from_local_producer, pressed_tile_data_dict["tile_x"],
                                 pressed_tile_data_dict["tile_y"], pressed_tile_data_dict["left_released"],
                                 pressed_tile_data_dict["right_released"]])
            print(action_queue)

def event_consumer(game_board, topic_name):
    #print('beginning of event consumer')
    # TODO: consider removing kafka thread and removing the action queue
    kafka_consumer_thread = threading.Thread(target=kafka_consumer, args=[topic_name])
    kafka_consumer_thread.start()

    global run
    while run:
        if len(action_queue) != 0:
            [from_local_producer, action_tile_x, action_tile_y, action_left_released, action_right_released] = \
                action_queue.pop(0)
            print("pop from action queue")
            # game state is updated according to the pressed button
            if (action_left_released or action_right_released):
                if not game_board.game_started and action_left_released and not action_right_released:
                    game_board.game_start_time = time.time()
                    game_board.game_started = True
                game_board.update_game_state(from_local_producer, action_tile_x, action_tile_y, action_left_released,
                                             action_right_released)

        game_board.update_board_for_display()
        game_board.display_game_board()
        if game_board.add_score:
            # TODO: fix bug - when pygame and highscore windows are open, if X is pressed in pygame win, all windows get stuck.
            # TODO: Detect click outside window from display HS func
            add_high_score(game_board, game_board.time, game_board.size_index)
        game_board.is_game_over()
        game_board.update_clock()
        pygame.display.update()

    #print("event_consumer quitting")


def get_tile_data_dict(producer_id, tile_x, tile_y, left_released, right_released):
    # data preparation for sending to consumer (should be possible to convert to json)
    return {'producer_id': producer_id ,'tile_x': tile_x, 'tile_y': tile_y, 'left_released': left_released,
            'right_released': right_released}


def main(size_index, num_of_tiles_x, num_of_tiles_y, num_of_mines):  # TODO: add comments
    #print("main start, threads: {}".format( threading.active_count() ))
    global producer_id
    producer_id = random.randint(0, prod_id_max_val)  # needs to come before random seed, to get unique producer_id

    # TODO: add Tkinter functionality to choose seed
    random_seed = 1     # random_seed generates a specific board setup for all users who enter this seed
    np.random.seed(random_seed)
    game_board = Board(size_index, num_of_tiles_x, num_of_tiles_y, num_of_mines)
    game_board.place_objects_in_array()
    game_board.count_num_of_touching_mines()
    left_pressed = False
    right_pressed = False
    LEFT = 1
    RIGHT = 3

    global run
    run = True

    # kafka vars
    # each seed (seed == board setup) has its own topic, to pass messages only between prod/cons of this seed
    topic_name = str(random_seed)
    kafka_server = 'localhost:9092'

    # starting consumer thread for kafka use
    consumer_thread = threading.Thread(target=event_consumer, args=[game_board, topic_name])
    consumer_thread.start()

    # start kafka producer
    producer = KafkaProducer(bootstrap_servers=kafka_server,
                             value_serializer=lambda data: json.dumps(data).encode('utf-8'))

    while run:
        """if left_released:
            print("clear left_released")"""
        left_released = False
        right_released = False
        for event in pygame.event.get():
            mouse_position = pygame.mouse.get_pos()

            if event.type == pygame.QUIT:
                run = False
                producer.send(topic_name, {'quit': 'quit'})
                producer.flush()

            # new game button pressed
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == LEFT and \
               game_board.is_mouse_over_new_game_button(mouse_position):
                game_board.board_init()
                game_board.place_objects_in_array()
                game_board.count_num_of_touching_mines()
                left_pressed = False
                right_pressed = False

            # if player hits a mine (loses), the game board freezes, not allowing further tile opening
            elif game_board.hit_mine:
                pass

            # detection of mouse button press
            elif event.type == pygame.MOUSEBUTTONDOWN and (event.button == LEFT or event.button == RIGHT):
                if event.button == LEFT:
                    left_pressed = True
                if event.button == RIGHT:
                    right_pressed = True


            elif event.type == pygame.MOUSEBUTTONUP and (event.button == LEFT or event.button == RIGHT):
                #detection of mouse button release, game state will be updated once mouse button is released
                if left_pressed and not right_pressed:
                    left_released = True
                if right_pressed and not left_pressed:
                    right_released = True
                if right_pressed and left_pressed:
                    left_released = True
                    right_released = True

                pixel_x = event.pos[0]
                pixel_y = event.pos[1]
                tile_xy = game_board.pixel_xy_to_tile_xy(pixel_x, pixel_y)
                tile_x = tile_xy[0]
                tile_y = tile_xy[1]

                # send to consumers clicks on game tiles only (x>=0, y>=0)
                # TODO: add condition on upper bound (tile_x <= ...)
                if tile_x >= 0 and tile_y >= 0:
                    tile_data_dict = get_tile_data_dict(producer_id, tile_x, tile_y, left_released, right_released)

                    # TODO: test efficiency of sending bytes vs. json
                    producer.send(topic_name, tile_data_dict)
                    producer.flush()

                # TODO: remove next 3 lines
                #global action_queue
                #action_queue.append([tile_x, tile_y, left_released, right_released])
                #print('appended to moves_queue:', tile_x, tile_y, left_released, right_released)
                left_pressed = False
                right_pressed = False

    time.sleep(1)   # wait 1 sec to avoid thread crash on pygame command
    pygame.quit()


open_opening_window()