from tkinter import messagebox
from Board import Board
import random
import pygame
import time
import threading
from kafka import KafkaConsumer
from kafka import KafkaProducer
from kafka.errors import (NoBrokersAvailable)
from certificate import *
from functools import partial
pygame.init()


class MinesweeperMain:
    # board size constants
    num_of_tiles_x_small_board = 10
    num_of_tiles_y_small_board = 10
    num_of_mines_small_board   = 10

    num_of_tiles_x_medium_board = 40
    num_of_tiles_y_medium_board = 40
    num_of_mines_medium_board   = int(0.2 * num_of_tiles_x_medium_board * num_of_tiles_y_medium_board) # 20% mines

    num_of_tiles_x_large_board = 300
    num_of_tiles_y_large_board = 300
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
    certificate_mode = True
    game_mode = False
    master_update_timeout = 1.5   # maximum expected time to receive potential master messages from all players [sec]


    def __init__(self):
        self.is_certificate = self.game_mode  # default is game_mode
        self.game_init()
        self.action_queue = []
        self.kafka_server = 'localhost:9092'
        self.producer_id = 0
        self.player_name = ""
        self.game_number_str = ""
        self.topic_name = ""
        self.tiles_to_update_for_new_player_array = None    # array with 1 for shown or flag tile, 0 for hidden tile

    def game_init(self):
        self.size_index = 0
        self.num_of_players = 1
        self.run = True
        self.game_started = False
        self.joining_time = time.time()
        if self.is_certificate:  # certificate mode
            self.i_am_master = False
        else:               # game mode
            self.i_am_master = True
        self.potential_master = False
        self.new_master_needed = False
        self.potential_master_counter = 0
        self.num_of_players = 1
        self.send_board_to_new_player = False
        self.board_sync_needed = False
        self.earliest_joining_time_of_received_board = self.joining_time
        self.timer_started = False

    def open_opening_window(self):
        opening_window = Tk()
        opening_window.title("Opening window")

        MODES = [("Small", self.SMALL), ("Medium", self.MEDIUM), ("Large", self.LARGE)]
        board_size = StringVar()
        board_size.set(self.SMALL)

        for mode, size in MODES:
            Radiobutton(opening_window, text=mode, variable=board_size, value=size).pack()  # radiobuttons for size choice

        name_description = Label(opening_window, text="Enter name: ")
        name_description.pack()
        name = Entry(opening_window, width=10)
        name.pack()
        # players need to enter the same game number to play on the same board
        game_number_description = Label(opening_window, text="Enter game number: ")
        game_number_description.pack()
        game_number = Entry(opening_window, width=10)
        game_number.pack()

        start_game_button = Button(opening_window, text="Start game", command=partial(self.start_new_game,
                                                                                      opening_window, board_size, game_number,
                                                                                      name))
        start_game_button.pack()

        # entry box for players to enter certificate, to view opened board and score
        certificate_description = Label(opening_window, text="Enter certificate: ")
        certificate_description.pack()
        certificate = Entry(opening_window, width=10)
        certificate.pack()  #TODO: add space between certificate entry box and button

        enter_certificate_button = Button(opening_window, text="Process certificate", command=partial(self.process_certificate,
                                                                                      opening_window, board_size, certificate))
        enter_certificate_button.pack()

        def on_closing():
            if messagebox.askokcancel("Quit", "Do you want to quit?"):
                opening_window.destroy()

        opening_window.protocol("WM_DELETE_WINDOW", on_closing)
        opening_window.mainloop()


    def start_new_game(self, opening_window, board_size, game_number, name):
        # function is called when pressing on start game button in opening window
        self.is_certificate = self.game_mode
        self.game_init()
        # self.joining_time = time.time()
        board_size_str = board_size.get()
        self.size_index = int(board_size_str)
        self.game_number_str = game_number.get()
        name_str = name.get()
        if self.game_number_str.isdigit() and name_str != "":
            game_number_int = int(self.game_number_str)
            self.player_name = name_str
            opening_window.destroy()
            self.main(game_number_int, self.game_mode)
            self.open_opening_window()
        elif name_str == "":
            messagebox.showwarning("Invalid input", "Invalid input, please enter your name")
        else:
            messagebox.showwarning("Invalid input", "Invalid input, please enter a whole number")


    def process_certificate(self, opening_window, board_size, certificate):
        # function is called when pressing on process certificate button in opening window
        self.is_certificate = self.certificate_mode
        self.game_init()
        cert_str = certificate.get()
        if is_valid_certificate(cert_str):  # TODO: add logic that gets score from certificate code and displays it
            cert_int = int(cert_str)
            board_size_str = board_size.get()
            self.size_index = int(board_size_str)
            opening_window.destroy()
            self.main(cert_int, self.certificate_mode)
            self.open_opening_window()


    def calculate_array_shape_for_sending(self):
        # one dimensional array is sent, shape should be [1, total num of tiles]
        num_of_tiles_x = self.board_info[self.size_index][0]
        num_of_tiles_y = self.board_info[self.size_index][1]
        return [1, num_of_tiles_x * num_of_tiles_y]


    def prepare_numpy_arrays_for_sending(self, game_board):     # returns list of two lists
        array_shape_for_sending = self.calculate_array_shape_for_sending()
        shown_array_for_sending = game_board.shown_array.reshape(array_shape_for_sending).astype(dtype=bool)
        flags_array_for_sending = game_board.flags_array.reshape(array_shape_for_sending).astype(dtype=bool)
        shown_and_flags_array_for_sending = np.logical_or(shown_array_for_sending, flags_array_for_sending).tolist()

        return shown_and_flags_array_for_sending


    def start_kafka_consumer(self):
        try:
            consumer = KafkaConsumer(self.topic_name, value_deserializer=lambda data: json.loads(data.decode('utf-8')))
        except NoBrokersAvailable:
            consumer = []
            print("Consumer not available. Please start zookeeper and kafka server")
            self.run = False
        except Exception as e:
            print("General server error")
            print(e)
            self.run = False

        return consumer


    def start_kafka_producer(self):
        try:
            # start kafka producer
            producer = KafkaProducer(bootstrap_servers=self.kafka_server,
                                     value_serializer=lambda data: json.dumps(data).encode('utf-8'))
            print("producer", producer)
            return producer # TODO: check what is the best practice here, maybe init to None

        except NoBrokersAvailable:
            print("Producer not available. Please start zookeeper and kafka server")
            self.run = False
        except Exception as e:
            print("General server error")
            print(e)
            self.run = False


    def send_joining_message(self, kafka_producer):
        if kafka_producer is not None:
            kafka_producer.send(self.topic_name, {'producer_id': self.producer_id,
                                                  'msg_type': 'control',
                                                  'msg': 'joining'})
            print("sending joining")
            kafka_producer.flush()


    def send_quitting_message(self, kafka_producer):
        if kafka_producer is not None:
            kafka_producer.send(self.topic_name, {'producer_id': self.producer_id,
                                                  'msg_type': 'control',
                                                  'msg': 'quitting',
                                                  'i_am_master': self.i_am_master})
            kafka_producer.flush()


    def send_tile_data_message(self, kafka_producer, tile_x, tile_y, left_released, right_released):
        if kafka_producer is not None:
            tile_data_dict = self.create_tile_data_dict(tile_x, tile_y, left_released, right_released)
            kafka_producer.send(self.topic_name, tile_data_dict)
            kafka_producer.flush()


    def send_welcome_msg(self, kafka_producer):
        # master sends joining time for deciding who is better master
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
                                              'board_array': board_array,
                                              'joining_time': self.joining_time})
        #print('sent board')
        kafka_producer.flush()


    def send_new_master_msg(self, kafka_producer):
        # msg is sent after master has left to decide who is the new master
        kafka_producer.send(self.topic_name, {'producer_id': self.producer_id,
                                              'msg_type': 'control',
                                              'msg': 'choosing_new_master',
                                              'joining_time': self.joining_time})
        kafka_producer.flush()


    def send_master_messages(self, kafka_producer, game_board):
        while self.run:
            if self.i_am_master and self.send_board_to_new_player:  # send msg to new players
                print('sending msg to new players')
                self.send_board_to_new_player = False   # clear before sending msgs to avoid missing new player
                self.send_welcome_msg(kafka_producer)
                arrays_for_sending_list = self.prepare_numpy_arrays_for_sending(game_board)
                self.send_game_board_to_new_player(kafka_producer, arrays_for_sending_list)
                print('board sent to new player')


            elif self.new_master_needed: # master has left and new master needs to be chosen
                self.send_new_master_msg(kafka_producer)
                self.new_master_needed = False

            time.sleep(1) # sleep for 1 sec


    def decide_whether_i_am_master(self, message, potential_master_decision):
        joining_time_msg = message.value.get('joining_time')

        # person who joined earlier will be the master (for sending already opened board to new joiners)
        # or potential master for choosing new master after master has left
        if joining_time_msg < self.joining_time:
            if potential_master_decision:
                self.potential_master = False
            else:   # decision who is original master (not after master has left)
                self.i_am_master = False

        # if two people joined at the same time, lower producer_id will remain master/potential master
        elif joining_time_msg == self.joining_time:
            producer_id_msg = message.value.get('producer_id')
            if producer_id_msg < self.producer_id:
                if potential_master_decision:
                    self.potential_master = False
                else:   # decision who is original master (not after master has left)
                    self.i_am_master = False


    def kafka_consumer(self):
        consumer = self.start_kafka_consumer()

        for message in consumer:
            # message.value contains dict with pressed tile data or 'quit' command
            producer_id_from_kafka = message.value['producer_id']
            from_local_producer = (producer_id_from_kafka == self.producer_id)
            msg_type = message.value.get('msg_type')
            #print("message received, type: ", msg_type)

            if msg_type == 'control':
                msg = message.value.get('msg')
                # checking run flag to close only local consumer
                if msg == 'joining' and not from_local_producer:
                    #       * game_master can send board to joining players (instead of kafka)
                    self.num_of_players += 1

                    # send_board_to_new_player becomes true for all players to not miss new player that needs the board
                    # when master leaves and new player joins before new master is chosen
                    self.send_board_to_new_player = True

                if msg == 'welcome':
                    self.decide_whether_i_am_master(message, potential_master_decision=False)
                    print("I am Master: ", self.i_am_master)

                    self.num_of_players = message.value.get('num_of_players')  # num of players received from game master

                elif msg == 'quitting':
                    i_am_master_msg = message.value.get('i_am_master')
                    if from_local_producer:
                        #print('killing local kafka consumer')
                        break   # don't delete, important for correct num_of_players
                    else:
                        self.num_of_players -= 1
                        #print('quitting msg received, num of players is ', self.num_of_players)
                        if i_am_master_msg and not from_local_producer:
                            self.new_master_needed = True
                            self.potential_master = True

                elif msg == 'choosing_new_master':
                    self.decide_whether_i_am_master(message, potential_master_decision=True)

            elif msg_type == 'data':
                pressed_tile_data_dict = message.value
                self.action_queue.append([from_local_producer,
                                          pressed_tile_data_dict["tile_x"], pressed_tile_data_dict["tile_y"],
                                          pressed_tile_data_dict["left_released"], pressed_tile_data_dict["right_released"]])
                print(self.action_queue)

            elif msg_type == 'board_for_new_player':
                print("board received from master")
                if not from_local_producer:
                    if not self.i_am_master:
                        self.send_board_to_new_player = False

                    joining_time_msg = message.value.get('joining_time')
                    # user updates his board if a message arrives with "better" board, from master with earlier joining time
                    if joining_time_msg < self.earliest_joining_time_of_received_board:
                        self.earliest_joining_time_of_received_board = joining_time_msg
                        shown_and_flags_list_for_new_player = message.value
                        shown_and_flags_array_for_new_player = np.asarray(shown_and_flags_list_for_new_player['board_array'])
                        num_of_tiles_x = self.board_info[self.size_index][0]
                        num_of_tiles_y = self.board_info[self.size_index][1]
                        self.tiles_to_update_for_new_player_array = np.reshape(shown_and_flags_array_for_new_player,
                                                                               [num_of_tiles_y, num_of_tiles_x]).astype(dtype=np.uint8)
                        self.board_sync_needed = True
                    else:
                        continue


    def synchronize_board_for_new_player(self, game_board):
        self.board_sync_needed = False
        flags_array_for_new_player = np.logical_and(self.tiles_to_update_for_new_player_array, game_board.mines_array)
        shown_array_for_new_player = np.logical_and(self.tiles_to_update_for_new_player_array, np.logical_not(game_board.mines_array))
        game_board.flags_array = np.logical_or(game_board.flags_array, flags_array_for_new_player)
        game_board.shown_array = np.logical_or(game_board.shown_array, shown_array_for_new_player)
        game_board.update_board_for_display_new_player()


    def event_consumer(self, game_board):
        if not self.is_certificate: # game_mode
            kafka_consumer_thread = threading.Thread(target=self.kafka_consumer)
            kafka_consumer_thread.start()

        while self.run:
            if self.potential_master:
                if not self.timer_started:  # start timer first time player becomes potential master
                    print("reset timer")
                    timer_start_time = time.perf_counter()
                    self.timer_started = True
                else:
                    timer_end_time = time.perf_counter()
                    elapsed_time = timer_end_time - timer_start_time
                    if elapsed_time > self.master_update_timeout:
                        # enough time has passed to decide that I am the new master (all messages received, no better master found)
                        self.i_am_master = self.potential_master
                        self.potential_master = False
                        self.potential_master_counter = 0

                        print("DBG: I am new Master: ", self.i_am_master)
                        print("DBG: Elapsed time: ", elapsed_time)
                        self.timer_started = False
            else:   # stop timer if decided that I am not potential master
                if self.timer_started:
                    self.timer_started = False


            if self.board_sync_needed:
                print('DBG: entering self.board_sync_needed')
                self.synchronize_board_for_new_player(game_board)

            elif len(self.action_queue) != 0:
                [from_local_producer, action_tile_x, action_tile_y, action_left_released, action_right_released] = \
                    self.action_queue.pop(0)
                #print("pop from action queue")
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
            if game_board.timeout:
                game_board.display_timeout_icon()

            game_board.update_clock()
            pygame.display.update()
            if game_board.is_game_over() and not game_board.game_over:
                show_certificate_code(game_board, self.game_number_str, self.player_name)
                game_board.game_over = True


    def create_tile_data_dict(self, tile_x, tile_y, left_released, right_released):
        # data preparation for sending to consumer (should be possible to convert to json)
        return {'msg_type': 'data',
                'producer_id': self.producer_id,
                'tile_x': tile_x,
                'tile_y': tile_y,
                'left_released': left_released,
                'right_released': right_released}


    def main(self, game_number, certificate_mode):  # TODO: add comments
        print("main start, threads: {}".format( threading.active_count() ))
        self.producer_id = random.randint(0,
                                     self.prod_id_max_val)  # needs to come before random seed, to get unique producer_id

        set_random_seed(game_number)
        (num_of_tiles_x, num_of_tiles_y, num_of_mines) = self.board_info[self.size_index]
        # board init
        game_board = Board(self.size_index, num_of_tiles_x, num_of_tiles_y, num_of_mines, certificate_mode)
        game_board.gen_random_mines_array()  # TODO: consider turning game_board into class attribute
        game_board.count_num_of_touching_mines()

        if certificate_mode:
            game_board.update_finished_board_for_display()
        left_pressed, right_pressed = [False, False]

        self.run = True

        # kafka vars
        # each game_number and board size has its own topic, to pass messages only between prod/cons of this game_number
        self.topic_name = "{}-{}".format(str(game_number), self.size_index)

        # starting consumer thread for kafka use
        consumer_thread = threading.Thread(target=self.event_consumer, args=[game_board])
        consumer_thread.start()

        producer = None  # no producer needed in certificate_mode
        if not self.is_certificate:     # start producer when in game_mode
            producer = self.start_kafka_producer()

        if self.run:
            if producer is not None:
                # start thread for game master to send messages
                master_thread = threading.Thread(target=self.send_master_messages, args=[producer, game_board])
                master_thread.start()

            if not self.game_started:  # send control msg "joining" only once
                self.send_joining_message(producer)
                self.game_started = True

        while self.run:
            left_released, right_released = [False, False]

            if game_board.timeout:  # timeout freezes game if mine was pressed/wrong flag
                game_board.dec_timeout_counter()

            for event in pygame.event.get():
                mouse_position = pygame.mouse.get_pos()

                if event.type == pygame.QUIT:
                    self.send_quitting_message(producer)
                    self.run = False

                if event.type == pygame.KEYDOWN:    # moving window on larger game board
                    if event.key == pygame.K_LEFT:
                        game_board.update_window_location(-1, 0)
                    if event.key == pygame.K_RIGHT:
                        game_board.update_window_location(1, 0)
                    if event.key == pygame.K_UP:
                        game_board.update_window_location(0, -1)
                    if event.key == pygame.K_DOWN:
                        game_board.update_window_location(0, 1)

                # new game button pressed (if enabled)
                if self.display_new_button_icon and event.type == pygame.MOUSEBUTTONDOWN and event.button == self.LEFT and \
                        game_board.is_mouse_over_new_game_button(mouse_position):
                    game_board.board_init(self.certificate_mode)
                    game_board.gen_random_mines_array()
                    game_board.count_num_of_touching_mines()
                    left_pressed, right_pressed = [False, False]

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

                # detection of mouse button release, game state will be updated once mouse button is released
                elif event.type == pygame.MOUSEBUTTONUP and (event.button == self.LEFT or event.button == self.RIGHT):
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
                            self.send_tile_data_message(producer, tile_x, tile_y, left_released, right_released)

                    left_pressed, right_pressed = [False, False]

        time.sleep(1)  # wait 1 sec to avoid thread crash on pygame command
        pygame.quit()
        self.game_started = False


game = MinesweeperMain()
game.open_opening_window()