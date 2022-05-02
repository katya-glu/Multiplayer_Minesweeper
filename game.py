from plot_high_score_class import HighScore
from tkinter import *
from tkinter import messagebox
from Board import Board
import random
import pygame
import time
from datetime import datetime
import numpy as np
import threading
from kafka import KafkaConsumer
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient
from kafka.errors import (UnknownTopicOrPartitionError)
import json
from pytictoc import TicToc
pygame.init()


# board size constants
num_of_tiles_x_small_board = 13
num_of_tiles_y_small_board = 15
num_of_mines_small_board = 40

num_of_tiles_x_medium_board = 40
num_of_tiles_y_medium_board = 40
num_of_mines_medium_board = int(0.2 * num_of_tiles_x_medium_board * num_of_tiles_y_medium_board) # 20% mines

num_of_tiles_x_large_board = 500
num_of_tiles_y_large_board = 500
num_of_mines_large_board = int(0.2 * num_of_tiles_x_large_board * num_of_tiles_y_large_board) # 20% mines

# constants
prod_id_max_val = (2 ** 32) - 1
timeout_val = 5000

# global vars
action_queue = []
run = True
producer_id = 0
game_started = False
timeout = False
timeout_counter = timeout_val

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
    # auto_offset_reset='earliest',
    consumer = KafkaConsumer(TOPIC_NAME,
                             value_deserializer=lambda data: json.loads(data.decode('utf-8')))
    global run

    connected_players_num = 0
    for message in consumer:
        # message.value contains dict with pressed tile data or 'quit' command
        msg_type = message.value.get('msg_type')
        #print('msg_type: ', msg_type)
        if msg_type == 'control':
            msg = message.value.get('msg')
            # checking run flag to close only local consumer
            if msg == 'joining':
                #print('joining')
                connected_players_num += 1
                #print('joining msg received, num of players is ', connected_players_num)
            if not run:
                #print('killing kafka consumer')
                connected_players_num -= 1
                #print('quitting msg received, num of players is ', connected_players_num)
                break

        # if quit_val == None, game continues for user
        if msg_type == 'data':
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

    #tictoc_timer = TicToc()
    #tictoc_timer.tic()
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
                #print("after update_game_state()")
                game_board.update_board_for_display(action_tile_x, action_tile_y)

        #print("start ", datetime.now())
        #tictoc_timer.toc('Section 1 took')
        #game_board.update_board_for_display()
        #print("after update_board_for_display() ", datetime.now())
        #tictoc_timer.toc('Section 2 took', restart=True)
        game_board.display_game_board()
        #print("after display_game_board() ", datetime.now())
        #tictoc_timer.toc('Section 3 took', restart=True)
        if game_board.add_score:
            # TODO: fix bug - when pygame and highscore windows are open, if X is pressed in pygame win, all windows get stuck.
            # TODO: Detect click outside window from display HS func
            add_high_score(game_board, game_board.time, game_board.size_index)
        global timeout
        if timeout:
            game_board.display_timeout_msg()
        game_board.is_game_over()
        game_board.update_clock()
        #tictoc_timer.toc('Section 4 took', restart=True)
        pygame.display.update()
        #print("end ", datetime.now())
        #print("after pygame.display.update()") TODO
        #tictoc_timer.toc('Section 5 took', restart=True)
        #tictoc_timer.toc(restart=True)

    #print("event_consumer quitting")


def get_tile_data_dict(producer_id, tile_x, tile_y, left_released, right_released):
    # data preparation for sending to consumer (should be possible to convert to json)
    return {'msg_type': 'data', 'producer_id': producer_id,'tile_x': tile_x, 'tile_y': tile_y, 'left_released': left_released,
            'right_released': right_released}


def main(size_index, num_of_tiles_x, num_of_tiles_y, num_of_mines):  # TODO: add comments
    #print("main start, threads: {}".format( threading.active_count() ))
    global producer_id
    producer_id = random.randint(0, prod_id_max_val)  # needs to come before random seed, to get unique producer_id

    # TODO: add Tkinter functionality to choose seed
    random_seed = 2     # random_seed generates a specific board setup for all users who enter this seed
    np.random.seed(random_seed)
    game_board = Board(size_index, num_of_tiles_x, num_of_tiles_y, num_of_mines)
    game_board.place_objects_in_array()
    tictoc_timer = TicToc()
    tictoc_timer.tic()
    game_board.count_num_of_touching_mines2()
    tictoc_timer.toc("count_num_of_touching_mines2")
    left_pressed = False
    right_pressed = False
    LEFT = 1
    RIGHT = 3

    global run, timeout, timeout_counter, timeout_val
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

    global game_started

    if not game_started:
        #print("game_started: ", game_started)
        producer.send(topic_name, {'msg_type': 'control', 'msg': 'joining'})
        producer.flush()
        game_started = True

    #print("game_started: ", game_started)
    while run:
        """if left_released:
            print("clear left_released")"""
        left_released = False
        right_released = False

        if timeout:     # timeout freezes game if mine was pressed
            if timeout_counter > 0:
                #game_board.display_timeout_msg()
                timeout_counter -= 1
                pygame.time.delay(1)
            else:
                global timeout_val
                timeout_counter = timeout_val
                timeout = False
                game_board.close_opened_mine_tile()
                print("timeout finished at ", datetime.now())

        for event in pygame.event.get():
            mouse_position = pygame.mouse.get_pos()

            if event.type == pygame.QUIT:
                run = False
                producer.send(topic_name, {'msg_type': 'control', 'msg': 'quit'})
                producer.flush()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    print("left key pressed")
                    game_board.update_window_location(-1, 0)
                    print("window location x is: ", game_board.window_loc_x)
                if event.key == pygame.K_RIGHT:
                    print("right key pressed")
                    game_board.update_window_location(1, 0)
                    print("window location x is: ", game_board.window_loc_x)
                if event.key == pygame.K_UP:
                    print("up key pressed")
                    game_board.update_window_location(0, -1)
                    print("window location y is: ", game_board.window_loc_y)
                if event.key == pygame.K_DOWN:
                    print("down key pressed")
                    game_board.update_window_location(0, 1)
                    print("window location y is: ", game_board.window_loc_y)

            # new game button pressed
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == LEFT and \
               game_board.is_mouse_over_new_game_button(mouse_position):
                game_board.board_init()
                game_board.place_objects_in_array()
                game_board.count_num_of_touching_mines2()
                left_pressed = False
                right_pressed = False

            # detection of click on radar
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == LEFT and \
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

                pixel_x = event.pos[0]
                pixel_y = event.pos[1]
                tile_x, tile_y = game_board.pixel_xy_to_tile_xy(pixel_x, pixel_y)

                # send to consumers when not in hit_mine freeze
                if game_board.is_mouse_over_window(mouse_position):
                    if not timeout and not game_board.is_mine(tile_x, tile_y, left_released, right_released):
                        # get_tile_data_dict func adds a {'msg_type': 'data'} key-value pair
                        tile_data_dict = get_tile_data_dict(producer_id, tile_x, tile_y, left_released, right_released)

                        # TODO: test efficiency of sending bytes vs. json
                        producer.send(topic_name, tile_data_dict)
                        producer.flush()

                    elif not timeout and game_board.is_mine(tile_x, tile_y, left_released, right_released):
                        action_queue.append([True, tile_x, tile_y, left_released, right_released]) # 0th index - from local producer
                        timeout = True
                        timeout_counter -= 1
                        print("timeout started at ", datetime.now())


                # TODO: remove next 3 lines
                #global action_queue
                #action_queue.append([tile_x, tile_y, left_released, right_released])
                #print('appended to moves_queue:', tile_x, tile_y, left_released, right_released)
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