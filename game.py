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
#from kafka.admin import KafkaAdminClient                  # used for deleting a topic (not supported by Win-Kafka
#from kafka.errors import (UnknownTopicOrPartitionError)   # used for deleting a topic (not supported by Win-Kafka
import json
#from pytictoc import TicToc                               # used to evaluate performance
pygame.init()


# board size constants
num_of_tiles_x_small_board = 40
num_of_tiles_y_small_board = 40
num_of_mines_small_board   = 1

num_of_tiles_x_medium_board = 40
num_of_tiles_y_medium_board = 40
num_of_mines_medium_board   = int(0.2 * num_of_tiles_x_medium_board * num_of_tiles_y_medium_board) # 20% mines

num_of_tiles_x_large_board = 500
num_of_tiles_y_large_board = 500
num_of_mines_large_board   = int(0.2 * num_of_tiles_x_large_board * num_of_tiles_y_large_board)    # 20% mines

board_info = [  (num_of_tiles_x_small_board , num_of_tiles_y_small_board , num_of_mines_small_board ),
                (num_of_tiles_x_medium_board, num_of_tiles_y_medium_board, num_of_mines_medium_board),
                (num_of_tiles_x_large_board , num_of_tiles_y_large_board , num_of_mines_large_board )  ]

# constants
prod_id_max_val = (2 ** 32) - 1
LEFT   = 1
RIGHT  = 3
SMALL  = 0
MEDIUM = 1
LARGE  = 2
display_new_button_icon = False     # no new game button multiplayer

# global vars
action_queue = []
run          = True
producer_id  = 0
game_started = False
player_name = ""
seed_str_for_cert = ""
tiles_hidden = True
tiles_shown = False


def open_opening_window():   # TODO: add comments
    # Create an instance of the HighScore class
    high_scores = HighScore(True, 10, [10, 5], [True, False], "high_scores.pkl")

    opening_window = Tk()
    opening_window.title("Opening window")

    MODES = [("Small", SMALL), ("Medium", MEDIUM), ("Large", LARGE)]
    board_size = StringVar()
    board_size.set(SMALL)

    for mode, size in MODES:
        Radiobutton(opening_window, text=mode, variable=board_size, value=size).pack()

    name_description = Label(opening_window, text="Enter name: ")
    name_description.pack()
    name = Entry(opening_window, width=10)
    name.pack()
    seed_description = Label(opening_window, text="Enter number: ")
    seed_description.pack()
    seed = Entry(opening_window, width=10)
    seed.pack()

    def start_new_game():
        board_size_str = board_size.get()
        size_index = int(board_size_str)
        seed_str = seed.get()
        name_str = name.get()
        if seed_str.isdigit() and name_str != "":
            global player_name, seed_str_for_cert
            seed_str_for_cert = seed_str
            seed_int = int(seed_str)
            player_name = name_str
            opening_window.destroy()
            main(size_index, seed_int, tiles_hidden)
            open_opening_window()
        elif name_str == "":
            messagebox.showwarning("Invalid input", "Invalid input, please enter your name")
        else:
            messagebox.showwarning("Invalid input", "Invalid input, please enter a whole number")

    def is_valid_certificate(cert_str):
        return cert_str.isdigit()   # TODO: add function to parse cert

    def process_certificate():
        cert_str = certificate.get()
        if is_valid_certificate(cert_str):
            cert_int = int(cert_str)
            board_size_str = board_size.get()
            size_index = int(board_size_str)
            opening_window.destroy()
            main(size_index, cert_int, tiles_shown)
            open_opening_window()

    # TODO: consider adding multiplayer high-scores
    """def open_high_scores():
        if not high_scores.is_window_open():
            high_scores.load_scores_from_file()
            high_scores.display_high_scores_window()"""

    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            opening_window.destroy()

    start_game_button = Button(opening_window, text="Start game", command=start_new_game)
    start_game_button.pack()

    certificate_description = Label(opening_window, text="Enter certificate: ")
    certificate_description.pack()
    certificate = Entry(opening_window, width=10)
    certificate.pack()

    enter_certificate_button = Button(opening_window, text="Process certificate", command=process_certificate)
    enter_certificate_button.pack()

    # TODO: consider adding multiplayer high-scores (collect score from all current players)
    #high_scores_button = Button(opening_window, text="High scores", command=open_high_scores)
    #high_scores_button.pack()

    opening_window.protocol("WM_DELETE_WINDOW", on_closing)
    opening_window.mainloop()

def add_high_score(game_board, score, size_index):
    high_scores = HighScore(False, 10, [10, 5], [True, False], "high_scores.pkl")
    high_scores.add_new_high_score(score, size_index)
    game_board.add_score = False

def show_certificate_code(game_board):
    certficate_window = Tk()
    certficate_window.title("Certificate")
    global seed_str_for_cert, player_name
    certificate_code = "{},{},{}".format(str(game_board.score), seed_str_for_cert, player_name)
    certficate_label = Label(certficate_window, text=certificate_code)
    certficate_label.pack()
    certficate_window.mainloop()

def kafka_consumer(topic_name):
    TOPIC_NAME = topic_name
    # auto_offset_reset='earliest',   # TODO: not working in Windows Kafka - topic deletion crashes Kafka
    consumer = KafkaConsumer(TOPIC_NAME, value_deserializer=lambda data: json.loads(data.decode('utf-8')))
    global run

    connected_players_num = 0
    for message in consumer:
        # message.value contains dict with pressed tile data or 'quit' command
        msg_type = message.value.get('msg_type')
        if msg_type == 'control':
            msg = message.value.get('msg')
            # checking run flag to close only local consumer
            if msg == 'joining':   # TODO: send back welcome message (let joining player count current players)
                                   #       * game_master can send board to joining players (instead of kafka)
                #print('joining')
                connected_players_num += 1
                #print('joining msg received, num of players is ', connected_players_num)
            if not run:   # TODO: change to message quiting
                #print('killing kafka consumer')
                connected_players_num -= 1
                #print('quitting msg received, num of players is ', connected_players_num)
                break

        if msg_type == 'data':
            pressed_tile_data_dict = message.value
            producer_id_from_kafka = message.value['producer_id']
            global producer_id
            from_local_producer = (producer_id_from_kafka == producer_id)

            action_queue.append([from_local_producer,
                                 pressed_tile_data_dict["tile_x"],
                                 pressed_tile_data_dict["tile_y"],
                                 pressed_tile_data_dict["left_released"],
                                 pressed_tile_data_dict["right_released"]])
            print(action_queue)


def event_consumer(game_board, topic_name):
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
                game_board.update_board_for_display(action_tile_x, action_tile_y)

        game_board.display_game_board(display_new_button_icon)
        """if game_board.add_score:
            # TODO: fix bug - when pygame and highscore windows are open, if X is pressed in pygame win, all windows get stuck.
            # TODO: Detect click outside window from display HS func
            add_high_score(game_board, game_board.time, game_board.size_index)"""
        if game_board.timeout:
            game_board.display_timeout_icon()

        game_board.update_clock()
        pygame.display.update()
        if game_board.is_game_over() and not game_board.game_over:
            #show_certificate_code(game_board)
            game_board.game_over = True


def create_tile_data_dict(producer_id, tile_x, tile_y, left_released, right_released):
    # data preparation for sending to consumer (should be possible to convert to json)
    return {'msg_type'      : 'data',
            'producer_id'   : producer_id,
            'tile_x'        : tile_x,
            'tile_y'        : tile_y,
            'left_released' : left_released,
            'right_released': right_released}


def main(size_index, seed, tiles_hidden):  # TODO: add comments
    #print("main start, threads: {}".format( threading.active_count() ))
    global producer_id
    producer_id = random.randint(0, prod_id_max_val)  # needs to come before random seed, to get unique producer_id

    np.random.seed(seed)   # random_seed generates a specific board setup for all users who enter this seed
    (num_of_tiles_x, num_of_tiles_y, num_of_mines) = board_info[size_index]
    game_board = Board(size_index, num_of_tiles_x, num_of_tiles_y, num_of_mines, tiles_hidden)
    game_board.gen_random_mines_array()
    game_board.count_num_of_touching_mines()
    if not tiles_hidden:
        game_board.update_finished_board_for_display()
    left_pressed = False
    right_pressed = False

    global run, game_started
    run = True

    # kafka vars
    # each seed (seed == board setup) has its own topic, to pass messages only between prod/cons of this seed
    topic_name = str(seed)
    kafka_server = 'localhost:9092'

    # starting consumer thread for kafka use
    consumer_thread = threading.Thread(target=event_consumer, args=[game_board, topic_name])
    consumer_thread.start()

    # start kafka producer
    producer = KafkaProducer(bootstrap_servers=kafka_server,
                             value_serializer=lambda data: json.dumps(data).encode('utf-8'))

    if not game_started:   # send control msg "joining" only once
        producer.send(topic_name, {'msg_type': 'control', 'msg': 'joining'})
        producer.flush()
        game_started = True

    while run:
        left_released = False
        right_released = False

        if game_board.timeout:     # timeout freezes game if mine was pressed/wrong flag
            game_board.dec_timeout_counter()

        for event in pygame.event.get():
            mouse_position = pygame.mouse.get_pos()

            if event.type == pygame.QUIT:
                run = False
                producer.send(topic_name, {'msg_type': 'control', 'msg': 'quit'})
                producer.flush()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    game_board.update_window_location(-1, 0)
                if event.key == pygame.K_RIGHT:
                    game_board.update_window_location(1, 0)
                if event.key == pygame.K_UP:
                    game_board.update_window_location(0, -1)
                if event.key == pygame.K_DOWN:
                    game_board.update_window_location(0, 1)

            # new game button pressed
            if display_new_button_icon and event.type == pygame.MOUSEBUTTONDOWN and event.button == LEFT and \
               game_board.is_mouse_over_new_game_button(mouse_position):
                game_board.board_init()
                game_board.gen_random_mines_array()
                game_board.count_num_of_touching_mines()
                left_pressed = False
                right_pressed = False

            # detection of click on radar
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == LEFT and \
                 game_board.is_mouse_over_radar(mouse_position):
                game_board.radar_pixel_xy_to_new_window_loc(mouse_position)

            # detection of mouse button press
            elif event.type == pygame.MOUSEBUTTONDOWN and (event.button == LEFT or event.button == RIGHT):
                if event.button == LEFT:
                    left_pressed = True
                if event.button == RIGHT:
                    right_pressed = True


            elif event.type == pygame.MOUSEBUTTONUP and (event.button == LEFT or event.button == RIGHT):
                # detection of mouse button release, game state will be updated once mouse button is released
                if left_pressed and not right_pressed:
                    left_released = True
                if right_pressed and not left_pressed:
                    right_released = True
                if right_pressed and left_pressed:
                    left_released = True
                    right_released = True

                pixel_x, pixel_y = event.pos
                tile_x, tile_y = game_board.pixel_xy_to_tile_xy(pixel_x, pixel_y)

                # send to consumers when not in hit_mine freeze
                if game_board.is_mouse_over_window(mouse_position) and not game_board.timeout and \
                   game_board.is_valid_input(tile_x, tile_y, left_released, right_released):
                    # wrong left click (on mine)
                    if game_board.is_left_click_on_mine(tile_x, tile_y, left_released, right_released):
                        action_queue.append([True, tile_x, tile_y, left_released, right_released]) # 0th index - from local producer
                        game_board.start_timeout(tile_x, tile_y, game_board.MINE_ERROR)

                    # wrong right click (tile without mine was flagged)
                    elif game_board.is_wrong_right_click(tile_x, tile_y, left_released, right_released):
                        action_queue.append([True, tile_x, tile_y, left_released, right_released]) # 0th index - from local producer
                        game_board.start_timeout(tile_x, tile_y, game_board.FLAG_ERROR)

                    else:
                        # get_tile_data_dict generates 'data' msg
                        tile_data_dict = create_tile_data_dict(producer_id, tile_x, tile_y, left_released, right_released)
                        producer.send(topic_name, tile_data_dict)
                        producer.flush()

                left_pressed = False
                right_pressed = False

    time.sleep(1)   # wait 1 sec to avoid thread crash on pygame command
    pygame.quit()
    """admin_client = KafkaAdminClient(bootstrap_servers=kafka_server)
    #admin_client.delete_topics(topics=[topic_name])
    try:
        print("deleting topic: ", topic_name)
        admin_client.delete_topics(topics=topic_name)
        print("Topic Deleted Successfully")
    except UnknownTopicOrPartitionError as e:
        print("Topic Doesn't Exist")
    except  Exception as e:
        print(e)"""
    game_started = False


open_opening_window()