from plot_high_score_class import HighScore
from tkinter import *
from tkinter import messagebox
from Board import Board
import random
import pygame
import time
import numpy as np
import threading
from datetime import datetime
from kafka import KafkaConsumer
from kafka import KafkaProducer
#from kafka.admin import KafkaAdminClient                  # used for deleting a topic (not supported by Win-Kafka
#from kafka.errors import (UnknownTopicOrPartitionError)   # used for deleting a topic (not supported by Win-Kafka
import json
#from pytictoc import TicToc                               # used to evaluate performance
pygame.init()


class MinesweeperMain:
    # board size constants
    num_of_tiles_x_small_board = 10
    num_of_tiles_y_small_board = 10
    num_of_mines_small_board   = 10

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
    display_clock = False
    tiles_hidden = True
    tiles_shown = False


    def __init__(self):
        self.action_queue = []
        self.run = True
        self.game_started = False
        self.joining_time = time.time() # TODO: add logic for determining oldest master
        self.kafka_server = 'localhost:9092'
        self.producer_id = 0
        self.player_name = ""
        self.seed_str = ""
        self.topic_name = ""
        self.i_am_master = True
        self.num_of_players = 1
        self.send_board_to_new_player = False
        self.received_all_board_parts = False   # TODO: add logic get board parts from kafka
        self.num_of_received_board_parts = 0    # TODO: add logic get board parts from kafka
        self.board_sync_needed = False
        self.tiles_to_update_for_new_player_array = None    # array with 1 for shown or flag tile, 0 for hidden tile


    def game_init(self):
        self.num_of_players = 1

    def open_opening_window(self):  # TODO: add comments
        # Create an instance of the HighScore class
        high_scores = HighScore(True, 10, [10, 5], [True, False], "high_scores.pkl")

        opening_window = Tk()
        opening_window.title("Opening window")

        MODES = [("Small", self.SMALL), ("Medium", self.MEDIUM), ("Large", self.LARGE)]
        board_size = StringVar()
        board_size.set(self.SMALL)

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
            self.game_init()
            self.joining_time = time.time()
            board_size_str = board_size.get()
            size_index = int(board_size_str)
            self.seed_str = seed.get()
            name_str = name.get()
            if self.seed_str.isdigit() and name_str != "":
                seed_int = int(self.seed_str)
                self.player_name = name_str
                opening_window.destroy()
                self.main(size_index, seed_int, self.tiles_hidden)
                self.open_opening_window()
            elif name_str == "":
                messagebox.showwarning("Invalid input", "Invalid input, please enter your name")
            else:
                messagebox.showwarning("Invalid input", "Invalid input, please enter a whole number")

        def is_valid_certificate(cert_str):
            return cert_str.isdigit()  # TODO: add function to parse cert

        def process_certificate():
            cert_str = certificate.get()
            if is_valid_certificate(cert_str):
                cert_int = int(cert_str)
                board_size_str = board_size.get()
                size_index = int(board_size_str)
                opening_window.destroy()
                self.main(size_index, cert_int, self.tiles_shown)
                self.open_opening_window()

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
        # high_scores_button = Button(opening_window, text="High scores", command=open_high_scores)
        # high_scores_button.pack()

        opening_window.protocol("WM_DELETE_WINDOW", on_closing)
        opening_window.mainloop()

    """def add_high_score(self, game_board, score, size_index):
        high_scores = HighScore(False, 10, [10, 5], [True, False], "high_scores.pkl")
        high_scores.add_new_high_score(score, size_index)
        game_board.add_score = False"""


    def show_certificate_code(self, game_board):
        certficate_window = Tk()
        certficate_window.title("Certificate")
        certificate_code = "{},{},{}".format(str(game_board.score), self.seed_str, self.player_name)
        certficate_label = Label(certficate_window, text=certificate_code)
        certficate_label.pack()
        certficate_window.mainloop()


    def prepare_numpy_arrays_for_sending(self, game_board):     # returns list of two lists
        shown_array_for_sending = game_board.shown_array.reshape([1, 100]).astype(dtype=bool)
        flags_array_for_sending = game_board.flags_array.reshape([1, 100]).astype(dtype=bool)
        shown_and_flags_array_for_sending = np.logical_or(shown_array_for_sending, flags_array_for_sending).tolist()
        return shown_and_flags_array_for_sending


    def send_welcome_msg(self, kafka_producer):
        # master sends joining time for deciding
        kafka_producer.send(self.topic_name, {'producer_id': self.producer_id,
                                              'msg_type': 'control',
                                              'msg': 'welcome',
                                              'num_of_players': self.num_of_players,
                                              'joining_time': self.joining_time})
        kafka_producer.flush()


    def send_game_board_to_new_player(self, kafka_producer, board_array):
        kafka_producer.send(self.topic_name, {'producer_id': self.producer_id,
                                              'msg_type': 'board_for_new_player',
                                              'msg': 'board_for_new_player',
                                              'board_array': board_array})
        #print('sent board', board_array)
        kafka_producer.flush()


    def send_messages_to_new_players(self, kafka_producer, game_board):
        # TODO: consider not closing the thread when stopping being master - to not open new thread in case of becoming master again
        while self.run and self.i_am_master:
            if self.send_board_to_new_player:
                print('sending msg to new players')
                self.send_board_to_new_player = False   # clear before sending msgs to avoid missing new player
                self.send_welcome_msg(kafka_producer)
                arrays_for_sending_list = self.prepare_numpy_arrays_for_sending(game_board)
                self.send_game_board_to_new_player(kafka_producer, arrays_for_sending_list)

            time.sleep(1) # sleep for 1 sec

    def kafka_consumer(self):
        TOPIC_NAME = self.topic_name
        # auto_offset_reset='earliest',   # TODO: not working in Windows Kafka - topic deletion crashes Kafka
        consumer = KafkaConsumer(TOPIC_NAME, value_deserializer=lambda data: json.loads(data.decode('utf-8')))

        #connected_players_num = 0
        for message in consumer:
            # message.value contains dict with pressed tile data or 'quit' command
            producer_id_from_kafka = message.value['producer_id']
            from_local_producer = (producer_id_from_kafka == self.producer_id)
            msg_type = message.value.get('msg_type')
            if msg_type == 'control':
                msg = message.value.get('msg')
                # checking run flag to close only local consumer
                if msg == 'joining' and not from_local_producer:
                    #       * game_master can send board to joining players (instead of kafka)
                    self.num_of_players += 1
                    print('joining msg received, num of players is ', self.num_of_players)

                    if self.i_am_master:    # master player sends board data to new players
                        self.send_board_to_new_player = True
                if msg == 'welcome':
                    print("welcome msg received")
                    num_of_players_msg = message.value.get('num_of_players')  # num of players received from game master
                    self.num_of_players = num_of_players_msg
                elif msg == 'quitting':
                    if from_local_producer:
                        print('killing local kafka consumer')
                        break   # don't delete, important for correct num_of_players
                    else:
                        self.num_of_players -= 1
                        print('quitting msg received, num of players is ', self.num_of_players)

            elif msg_type == 'data':
                pressed_tile_data_dict = message.value
                #producer_id_from_kafka = message.value['producer_id']
                #from_local_producer = (producer_id_from_kafka == self.producer_id)

                self.action_queue.append([from_local_producer,
                                     pressed_tile_data_dict["tile_x"],
                                     pressed_tile_data_dict["tile_y"],
                                     pressed_tile_data_dict["left_released"],
                                     pressed_tile_data_dict["right_released"]])
                print(self.action_queue)

            elif msg_type == 'board_for_new_player':
                if not self.received_all_board_parts:
                    shown_and_flags_list_for_new_player = message.value
                    shown_and_flags_array_for_new_player = np.asarray(shown_and_flags_list_for_new_player['board_array'])
                    self.tiles_to_update_for_new_player_array = np.reshape(shown_and_flags_array_for_new_player, [10, 10]).astype(dtype=np.uint8)
                    print("board received", self.tiles_to_update_for_new_player_array)

                    self.board_sync_needed = True
                else:
                    continue


    def synchronize_board_for_new_player(self, game_board):
        self.board_sync_needed = False
        self.received_all_board_parts = True    # only one part at this point
        flags_array_for_new_player = np.logical_and(self.tiles_to_update_for_new_player_array, game_board.mines_array) #TODO find better name
        shown_array_for_new_player = np.logical_and(self.tiles_to_update_for_new_player_array, np.logical_not(game_board.mines_array))
        game_board.flags_array = np.logical_or(game_board.flags_array, flags_array_for_new_player)
        game_board.shown_array = np.logical_or(game_board.shown_array, shown_array_for_new_player)
        game_board.update_board_for_display_new_player()

        #self.shown_and_flags_array_for_new_player = None   # TODO: find a way to free memory

    def event_consumer(self, game_board):
        kafka_consumer_thread = threading.Thread(target=self.kafka_consumer)
        kafka_consumer_thread.start()

        while self.run:
            if self.board_sync_needed:
                print('entering self.board_sync_needed')
                #sync_thread = threading.Thread(target=self.synchronize_board_for_new_player, args=[game_board])
                #sync_thread.start()
                self.synchronize_board_for_new_player(game_board)  # TODO: display sync message
            elif len(self.action_queue) != 0:
                [from_local_producer, action_tile_x, action_tile_y, action_left_released, action_right_released] = \
                    self.action_queue.pop(0)
                print("pop from action queue")
                # game state is updated according to the pressed button
                if (action_left_released or action_right_released):
                    if not game_board.game_started and action_left_released and not action_right_released:
                        game_board.game_start_time = time.time()
                        game_board.game_started = True

                    game_board.update_game_state(from_local_producer, action_tile_x, action_tile_y,
                                                 action_left_released,
                                                 action_right_released)
                    game_board.update_board_for_display(action_tile_x, action_tile_y)

            game_board.display_game_board(self.display_new_button_icon, self.display_clock, self.num_of_players)
            """if game_board.add_score:
                # TODO: fix bug - when pygame and highscore windows are open, if X is pressed in pygame win, all windows get stuck.
                # TODO: Detect click outside window from display HS func
                add_high_score(game_board, game_board.time, game_board.size_index)"""
            if game_board.timeout:
                game_board.display_timeout_icon()

            game_board.update_clock()
            pygame.display.update()
            if game_board.is_game_over() and not game_board.game_over:
                # show_certificate_code(game_board)
                game_board.game_over = True


    def create_tile_data_dict(self, tile_x, tile_y, left_released, right_released):
        # data preparation for sending to consumer (should be possible to convert to json)
        return {'msg_type': 'data',
                'producer_id': self.producer_id,
                'tile_x': tile_x,
                'tile_y': tile_y,
                'left_released': left_released,
                'right_released': right_released}


    def main(self, size_index, seed, tiles_hidden):  # TODO: add comments
        print("main start, threads: {}".format( threading.active_count() ))
        self.producer_id = random.randint(0,
                                     self.prod_id_max_val)  # needs to come before random seed, to get unique producer_id

        np.random.seed(seed)  # random_seed generates a specific board setup for all users who enter this seed
        (num_of_tiles_x, num_of_tiles_y, num_of_mines) = self.board_info[size_index]
        game_board = Board(size_index, num_of_tiles_x, num_of_tiles_y, num_of_mines, tiles_hidden)
        game_board.gen_random_mines_array()  # TODO: consider turning game_board into class attribute
        game_board.count_num_of_touching_mines()

        if not tiles_hidden:
            game_board.update_finished_board_for_display()
        left_pressed = False
        right_pressed = False

        self.run = True

        # kafka vars
        # each seed (seed == board setup) has its own topic, to pass messages only between prod/cons of this seed
        self.topic_name = str(seed)


        # starting consumer thread for kafka use
        consumer_thread = threading.Thread(target=self.event_consumer, args=[game_board])
        consumer_thread.start()

        # start kafka producer
        producer = KafkaProducer(bootstrap_servers=self.kafka_server,
                                 value_serializer=lambda data: json.dumps(data).encode('utf-8'))

        # start thread for game master to check for new players
        if self.i_am_master:
            master_thread = threading.Thread(target=self.send_messages_to_new_players, args=[producer, game_board])
            master_thread.start()


        if not self.game_started:  # send control msg "joining" only once
            producer.send(self.topic_name, {'producer_id': self.producer_id,
                                            'msg_type': 'control',
                                            'msg': 'joining'})
            print("sending joining")
            producer.flush()
            self.game_started = True

        while self.run:
            left_released = False
            right_released = False

            if game_board.timeout:  # timeout freezes game if mine was pressed/wrong flag
                game_board.dec_timeout_counter()

            for event in pygame.event.get():
                mouse_position = pygame.mouse.get_pos()

                if event.type == pygame.QUIT:
                    #print("pygame QUIT event")
                    producer.send(self.topic_name, {'producer_id': self.producer_id,
                                                    'msg_type': 'control',
                                                    'msg': 'quitting'})
                    producer.flush()
                    #time.sleep(5)
                    self.run = False
                    #print("pygame QUIT event, after run=False")


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
                if self.display_new_button_icon and event.type == pygame.MOUSEBUTTONDOWN and event.button == self.LEFT and \
                        game_board.is_mouse_over_new_game_button(mouse_position):
                    game_board.board_init(self.tiles_hidden)
                    game_board.gen_random_mines_array()
                    game_board.count_num_of_touching_mines()
                    left_pressed = False
                    right_pressed = False

                # detection of click on radar
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == self.LEFT and \
                        game_board.is_mouse_over_radar(mouse_position):
                    game_board.radar_pixel_xy_to_new_window_loc(mouse_position)

                # detection of mouse button press
                elif event.type == pygame.MOUSEBUTTONDOWN and (event.button == self.LEFT or event.button == self.RIGHT):
                    if event.button == self.LEFT:
                        left_pressed = True
                    if event.button == self.RIGHT:
                        right_pressed = True

                elif event.type == pygame.MOUSEBUTTONUP and (event.button == self.LEFT or event.button == self.RIGHT):
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
                            self.action_queue.append([True, tile_x, tile_y, left_released,
                                                      right_released])  # 0th index - from local producer
                            game_board.start_timeout(tile_x, tile_y, game_board.MINE_ERROR)

                        # wrong right click (tile without mine was flagged)
                        elif game_board.is_wrong_right_click(tile_x, tile_y, left_released, right_released):
                            self.action_queue.append([True, tile_x, tile_y, left_released,
                                                      right_released])  # 0th index - from local producer
                            game_board.start_timeout(tile_x, tile_y, game_board.FLAG_ERROR)

                        else:
                            # get_tile_data_dict generates 'data' msg
                            tile_data_dict = self.create_tile_data_dict(tile_x, tile_y, left_released,
                                                                        right_released)
                            producer.send(self.topic_name, tile_data_dict)
                            producer.flush()

                    left_pressed = False
                    right_pressed = False

        time.sleep(1)  # wait 1 sec to avoid thread crash on pygame command
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
        self.game_started = False


game = MinesweeperMain()
print("game pointer: ", game)
game.open_opening_window()