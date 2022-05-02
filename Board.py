import numpy as np
import pygame
import time
from datetime import datetime


class Board:
    # shown array constants
    HIDDEN = 0
    SHOWN = 1

    # flags array constants
    # NO_FLAG = 0
    FLAGGED = 1

    # board for display constants
    TILE_EMPTY = 0
    # TWO-EIGHT = 2-8
    TILE_MINE = 9
    TILE_BLOCKED = 10
    TILE_FLAG = 11
    LOSING_MINE_RED = 13

    NEW_GAME_BUTTON = 12

    # score constants
    hit_mine_points = -10
    open_tile_points = 1

    # window constants
    window_num_of_tiles_x_var = 20
    window_num_of_tiles_y_var = 20
    block_color = (211, 211, 211)
    numbers_color = (180, 180, 180)
    win_frame_color = (0, 0, 255)
    mine_color = (220, 0, 0)
    flag_color = (30, 150, 30)
    black = (0, 0, 0)

    # list of tiles images. displayed according to index (value in board_for_display array)
    tiles = [pygame.image.load("empty.png"), pygame.image.load("one.png"), pygame.image.load("two.png"),
             pygame.image.load("three.png"), pygame.image.load("four.png"), pygame.image.load("five.png"),
             pygame.image.load("six.png"), pygame.image.load("seven.png"), pygame.image.load("eight.png"),
             pygame.image.load("mine.png"), pygame.image.load("block.png"), pygame.image.load("flagged.png"),
             pygame.image.load("new_game_unpressed.png"), pygame.image.load("mine_red.png")]

    def __init__(self, size_index, num_of_tiles_x, num_of_tiles_y, num_of_mines, tile_width=16, tile_height=16):
        pygame.init()
        self.size_index = size_index  # 0=small, 1=medium, 2=large
        self.num_of_tiles_x = num_of_tiles_x
        self.num_of_tiles_y = num_of_tiles_y
        self.board_shape = (num_of_tiles_y, num_of_tiles_x)
        self.num_of_mines = num_of_mines
        self.tile_width = tile_width
        self.tile_height = tile_height
        self.delta_from_left_x = 0
        self.delta_from_top_y = 50
        self.window_num_of_tiles_x = min(self.window_num_of_tiles_x_var, self.num_of_tiles_x)
        self.window_num_of_tiles_y = min(self.window_num_of_tiles_y_var, self.num_of_tiles_y)
        # radar size is ~160 pixels. radar_tile_size_px is derived from #tiles, but in range[1, 5]
        self.radar_tile_size_px = min(5, max(1, int(160/max(self.num_of_tiles_x, self.num_of_tiles_y))))
        self.radar_margin_size_px = 3
        self.radar_start_pos_x = self.window_num_of_tiles_x * self.tile_width + self.radar_margin_size_px
        self.radar_start_pos_y = self.delta_from_top_y + 3
        self.radar_width = self.num_of_tiles_x * self.radar_tile_size_px
        self.radar_height = self.num_of_tiles_y * self.radar_tile_size_px
        # self.radar_margin_size_px*2 - adding delta for margin on the left and right of the radar
        self.radar_width_w_margins = self.radar_width + self.radar_margin_size_px * 2
        self.radar_height_w_margins = self.radar_height + self.radar_margin_size_px * 2
        # radar_bg = pygame.image.load("radar_bg.png")
        self.radar_surface = pygame.Surface((self.radar_width, self.radar_height))
        self.radar_surface.fill(self.block_color)

        self.window_start_pos_x = self.delta_from_left_x
        self.window_start_pos_y = self.delta_from_top_y
        self.window_width       = self.window_num_of_tiles_x * self.tile_width
        self.window_height      = self.window_num_of_tiles_y * self.tile_height

        self.score_image = pygame.image.load("coin2.png")

        self.canvas_pixel_width = 0
        self.canvas_pixel_height = 0
        self.canvas = self.canvas_init()
        self.board_init()

    def board_init(self):
        self.win = False
        self.hit_mine = False
        self.game_over = False
        self.add_score = False
        self.game_started = False
        self.window_loc_x = 0
        self.window_loc_y = 0
        self.mine_loc_x = float('inf')
        self.mine_loc_y = float('inf')
        self.tile_offset_for_display_x = self.window_loc_x
        self.tile_offset_for_display_y = self.window_loc_y
        self.game_start_time = 0
        self.time = 0
        self.score = 0
        self.closed_tiles_num = self.num_of_tiles_x * self.num_of_tiles_y
        self.radar_surface.fill(self.block_color)
        self.clock_and_score_font = pygame.font.SysFont("consolas", 20)
        self.shown_array = np.zeros(self.board_shape, dtype=np.uint8)
        self.flags_array = np.zeros(self.board_shape, dtype=np.uint8)
        self.mines_array = np.zeros(self.board_shape, dtype=np.uint8)
        self.neighbours_array = np.zeros(self.board_shape, dtype=np.uint8)
        self.board_array = np.zeros(self.board_shape, dtype=np.uint8)
        self.board_for_display = np.full(self.board_shape, self.TILE_BLOCKED, dtype=np.uint8)
        self.new_button_icon = self.tiles[self.NEW_GAME_BUTTON]

    def canvas_init(self):
        self.canvas_pixel_width = self.delta_from_left_x + self.window_width + self.radar_width_w_margins
        self.canvas_pixel_height = max(self.delta_from_top_y + self.window_height,
                                       self.delta_from_top_y + self.radar_height_w_margins)
        canvas = pygame.display.set_mode((self.canvas_pixel_width, self.canvas_pixel_height))
        pygame.display.set_caption("Minesweeper")
        return canvas

    def place_objects_in_array(self):
        # function shuffles an array in order to randomly generate locations of objects in the array
        num_of_elements = self.num_of_tiles_x * self.num_of_tiles_y
        ones_array = np.ones(self.num_of_mines, dtype=int)
        zeros_array = np.zeros(num_of_elements - self.num_of_mines, dtype=int)
        joined_array = np.concatenate((ones_array, zeros_array))
        np.random.shuffle(joined_array)
        mines_array = joined_array.reshape(self.board_shape)
        self.mines_array = mines_array.astype(np.uint8)

    def count_num_of_touching_mines(self):
        # function receives an array with mines locations, calculates how many mines touch each empty cell
        padded_mines_array = np.pad(self.mines_array, (1, 1))
        for y in range(1, self.num_of_tiles_y + 1):
            for x in range(1, self.num_of_tiles_x + 1):
                if padded_mines_array[y][x] == 0:
                    self.neighbours_array[y - 1][x - 1] = np.sum(
                        padded_mines_array[y - 1:y + 2, x - 1:x + 2])  # sum elements around curr position
        self.board_array = self.neighbours_array + self.TILE_MINE * self.mines_array

    def count_num_of_touching_mines2(self):
        padded_mines_array = np.pad(self.mines_array, (1, 1))
        #print(padded_mines_array.dtype)
        sum = np.zeros(padded_mines_array.shape)
        sum += padded_mines_array
        padded_array1 = np.roll(padded_mines_array, -1, axis=0)  # n
        sum += padded_array1
        padded_array2 = np.roll(padded_array1, -1, axis=1)  # nw
        sum += padded_array2
        padded_array2 = np.roll(padded_array1, 1, axis=1)  # ne
        sum += padded_array2
        padded_array1 = np.roll(padded_mines_array, -1, axis=1)  # w
        sum += padded_array1
        padded_array1 = np.roll(padded_mines_array, 1, axis=1)  # e
        sum += padded_array1
        padded_array1 = np.roll(padded_mines_array, 1, axis=0)  # s
        sum += padded_array1
        padded_array2 = np.roll(padded_array1, -1, axis=1)  # sw
        sum += padded_array2
        padded_array2 = np.roll(padded_array1, 1, axis=1)  # se
        sum += padded_array2
        inverse_padded_array = np.logical_not(padded_mines_array)
        multiplication_result = np.multiply(inverse_padded_array, sum)
        #print(self.neighbours_array.dtype)
        self.neighbours_array = multiplication_result[1:-1, 1:-1]
        #print(self.neighbours_array.dtype)
        self.neighbours_array = self.neighbours_array.astype(np.uint8)
        #print(self.neighbours_array.dtype)

        self.board_array = self.neighbours_array + self.TILE_MINE * self.mines_array
        #print(self.board_array.dtype)


    def pixel_xy_to_tile_xy(self, pixel_x, pixel_y):
        tile_x = ((pixel_x - self.delta_from_left_x) // self.tile_width) + self.tile_offset_for_display_x
        tile_y = ((pixel_y - self.delta_from_top_y) // self.tile_height) + self.tile_offset_for_display_y
        return tile_x, tile_y

    def is_valid_input(self, tile_x, tile_y, left_click, right_click):
        """
        function checks whether the input is valid - click should be on a closed tile, left click opens tile, right
        click toggles flag display
        """
        if left_click and right_click:  # TODO: add functionality for incorrectly marked flags(lose)
            if self.shown_array[tile_y][tile_x] == self.SHOWN:
                padded_flags_array = np.pad(self.flags_array, (1, 1))
                padded_tile_x = tile_x + 1
                padded_tile_y = tile_y + 1
                num_of_flags_in_sub_array = np.sum(padded_flags_array[padded_tile_y - 1:padded_tile_y + 2,
                                                   padded_tile_x - 1:padded_tile_x + 2])
                if self.board_array[tile_y][tile_x] == num_of_flags_in_sub_array:
                    return True
                else:
                    return False
        if tile_x < 0 or tile_y < 0 or tile_x > (self.num_of_tiles_x - 1) or tile_y > (self.num_of_tiles_y - 1):
            return False
        if self.shown_array[tile_y][tile_x] == self.SHOWN:
            return False
        if left_click and not right_click:
            if self.flags_array[tile_y][tile_x] == self.FLAGGED:
                return False
            else:
                #print("valid left click")
                return True
        if right_click and not left_click:
            return True

    def flood_fill(self, tile_x, tile_y, left_and_right_click): # TODO: return number of tiles opened
        # flood fill algorithm - https://en.wikipedia.org/wiki/Flood_fill
        # func is being called only if the opened tile is empty
        flood_fill_queue = []
        opened_tiles_num = 0    # counting num of open tiles for score update
        if left_and_right_click:
            y_start = max(tile_y - 1, 0)
            y_end = min(tile_y + 2, self.num_of_tiles_y)
            x_start = max(tile_x - 1, 0)
            x_end = min(tile_x + 2, self.num_of_tiles_x)
            for curr_tile_y in range(y_start, y_end):  # TODO: switch to numpy operation
                for curr_tile_x in range(x_start, x_end):
                    #print('left and right click ff loop')
                    if self.shown_array[curr_tile_y][curr_tile_x] == self.HIDDEN and \
                            self.flags_array[curr_tile_y][curr_tile_x] != self.FLAGGED:
                        #print('left and right click ff loop hidden condition')
                        self.shown_array[curr_tile_y][curr_tile_x] = self.SHOWN
                        self.update_board_for_display(curr_tile_x, curr_tile_y)
                        opened_tiles_num += 1
                        #print('left and right click opened tiles num increase')
                    flood_fill_queue.append((curr_tile_y, curr_tile_x))
        else:
            if self.shown_array[tile_y][tile_x] == self.HIDDEN:
                self.shown_array[tile_y][tile_x] = self.SHOWN
                opened_tiles_num += 1
            flood_fill_queue = [(tile_y, tile_x)]

        while len(flood_fill_queue) != 0:
            curr_pos = flood_fill_queue.pop(0)
            curr_y = curr_pos[0]
            curr_x = curr_pos[1]
            if self.board_array[curr_y][curr_x] == self.TILE_EMPTY:
                for neighbour_y in range(curr_y - 1, curr_y + 2):
                    for neighbour_x in range(curr_x - 1, curr_x + 2):
                        if (neighbour_y <= (self.num_of_tiles_y - 1) and neighbour_y >= 0) and \
                           (neighbour_x <= (self.num_of_tiles_x - 1) and neighbour_x >= 0):
                            if self.shown_array[neighbour_y][neighbour_x] == self.HIDDEN:
                                flood_fill_queue.append((neighbour_y, neighbour_x))
                                self.shown_array[neighbour_y][neighbour_x] = self.SHOWN  # all neighbours change to shown
                                self.update_board_for_display(neighbour_x, neighbour_y)
                                opened_tiles_num += 1
        return opened_tiles_num

    def update_game_state(self, from_local_producer, tile_x, tile_y, left_click, right_click):
        # function updates game state upon receiving valid input
        if self.is_valid_input(tile_x, tile_y, left_click, right_click):  # shown_array[tile_y][tile_x] == self.HIDDEN
            if left_click and right_click:
                padded_flags_array = np.pad(self.flags_array, (1, 1))
                padded_mines_array = np.pad(self.mines_array, (1, 1))
                padded_tile_x = tile_x + 1
                padded_tile_y = tile_y + 1
                if (padded_flags_array[padded_tile_y - 1:padded_tile_y + 2, padded_tile_x - 1:padded_tile_x + 2]
                        == padded_mines_array[padded_tile_y - 1:padded_tile_y + 2, padded_tile_x - 1:padded_tile_x + 2]).all():
                    num_of_open_tiles = self.flood_fill(tile_x, tile_y, True)
                    self.closed_tiles_num -= num_of_open_tiles
                    if from_local_producer:
                        self.update_score(self.open_tile_points * num_of_open_tiles)
                else:
                    self.hit_mine = True
                    if from_local_producer:
                        self.update_score(self.hit_mine_points)
            elif left_click and self.board_array[tile_y][tile_x] != self.TILE_EMPTY:
                self.shown_array[tile_y][tile_x] = self.SHOWN
                if self.board_array[tile_y][tile_x] == self.TILE_MINE or self.board_array[tile_y][tile_x] == self.LOSING_MINE_RED:
                    self.hit_mine = True
                    self.board_array[tile_y][tile_x] = self.LOSING_MINE_RED
                    if from_local_producer:
                        self.update_score(self.hit_mine_points)
                # update score if empty tile opened and not hit_mine
                if from_local_producer and not self.hit_mine:
                    self.update_score(self.open_tile_points)
                    self.closed_tiles_num -= 1
            elif left_click and self.board_array[tile_y][tile_x] == self.TILE_EMPTY:
                #start_time = datetime.timestamp(datetime.now())
                #print("DEBUG: start_time ", datetime.now())
                num_of_open_tiles = self.flood_fill(tile_x, tile_y, False)
                self.closed_tiles_num -= num_of_open_tiles
                #end_time = datetime.timestamp(datetime.now())
                #elapsed_time = end_time - start_time
                #print("DEBUG: elapsed_time ", elapsed_time)

                if from_local_producer:
                    self.update_score(self.open_tile_points * num_of_open_tiles)
            elif right_click:
                self.flags_array[tile_y][tile_x] = self.FLAGGED - self.flags_array[tile_y][tile_x]  # toggle flag on/off
                if self.flags_array[tile_y][tile_x] == self.FLAGGED:    # flag added
                    self.closed_tiles_num -= 1
                else:                                                   # flag removed
                    self.closed_tiles_num += 1



    def update_board_for_display(self, curr_tile_x, curr_tile_y):
        """
        Function updates board for display - the appropriate sprite index in tiles list is updated in board_for_display,
        based on the shown array
        """


        # updating flags
        if self.flags_array[curr_tile_y][curr_tile_x] == self.FLAGGED:
            self.board_for_display[curr_tile_y][curr_tile_x] = self.TILE_FLAG
            self.radar_surface.fill(self.flag_color, (curr_tile_x * self.radar_tile_size_px,
                                                      curr_tile_y * self.radar_tile_size_px,
                                                      self.radar_tile_size_px, self.radar_tile_size_px))

        # updating mines, in case of losing
        elif self.hit_mine and self.board_array[curr_tile_y][curr_tile_x] == self.LOSING_MINE_RED:
            self.board_for_display[curr_tile_y][curr_tile_x] = self.board_array[curr_tile_y][curr_tile_x]
            self.radar_surface.fill(self.mine_color, (curr_tile_x * self.radar_tile_size_px,
                                                      curr_tile_y * self.radar_tile_size_px,
                                                      self.radar_tile_size_px, self.radar_tile_size_px))

        # updating blocks (hidden tiles)
        elif self.shown_array[curr_tile_y][curr_tile_x] == self.HIDDEN:
            self.board_for_display[curr_tile_y][curr_tile_x] = self.TILE_BLOCKED
            self.radar_surface.fill(self.block_color, (curr_tile_x * self.radar_tile_size_px,
                                                       curr_tile_y * self.radar_tile_size_px,
                                                       self.radar_tile_size_px, self.radar_tile_size_px))

        # updating numbers
        else:  # tile has been opened
            self.board_for_display[curr_tile_y][curr_tile_x] = self.board_array[curr_tile_y][curr_tile_x]
            self.radar_surface.fill(self.numbers_color, (curr_tile_x * self.radar_tile_size_px,
                                                         curr_tile_y * self.radar_tile_size_px,
                                                         self.radar_tile_size_px, self.radar_tile_size_px))


    def display_game_board(self):
        # background
        background_color = (0, 0, 0)
        self.canvas.fill(background_color)

        # display new game button
        self.canvas.blit(self.new_button_icon,
                         ((self.canvas_pixel_width - self.new_button_icon.get_width()) / 2, 2))  # TODO: remove magic number

        # display clock
        clock_text = self.clock_and_score_font.render('{0:03d}'.format(self.time), False, (255, 255, 255))
        self.canvas.blit(clock_text, (self.canvas_pixel_width - (clock_text.get_width() + 5), 5))  # TODO: remove magic number

        # display score
        self.canvas.blit(self.score_image,((5, 5)))
        score_text = self.clock_and_score_font.render('{0:03d}'.format(self.score), False, (255, 255, 255))
        self.canvas.blit(score_text, (8 + 16, 5))  # TODO: remove magic number

        # display num of remaining closed tiles
        self.canvas.blit(self.tiles[self.TILE_BLOCKED], ((5, 28)))
        closed_tiles_num_text = self.clock_and_score_font.render('{:,}'.format(self.closed_tiles_num), False, (255, 255, 255))
        #closed_tiles_num_text = self.clock_and_score_font.render('{}'.format(self.closed_tiles_num), False, (255, 255, 255))
        self.canvas.blit(closed_tiles_num_text, (8 + 16, 28))  # TODO: remove magic number

        # display radar
        color = (128, 128, 128)
        pygame.draw.rect(self.canvas, color,
                         (self.radar_start_pos_x - 2, self.radar_start_pos_y - 2, self.radar_width + 4, self.radar_height + 4), 2)
        self.display_radar()

        # display board
        min_tile_val_x = self.window_loc_x
        min_tile_val_y = self.window_loc_y
        max_tile_val_x = self.window_loc_x + self.window_num_of_tiles_x
        max_tile_val_y = self.window_loc_y + self.window_num_of_tiles_y
        #print("min_tile_val_x: {}, min_tile_val_y: {}, max_tile_val_x: {}, max_tile_val_y: {}".format(min_tile_val_x,min_tile_val_y,max_tile_val_x,max_tile_val_y))
        self.tile_offset_for_display_x = min_tile_val_x
        self.tile_offset_for_display_y = min_tile_val_y
        for tile_y in range(min_tile_val_y, max_tile_val_y):
            tile_pos_y = (tile_y - self.tile_offset_for_display_y) * self.tile_height + self.delta_from_top_y
            for tile_x in range(min_tile_val_x, max_tile_val_x):
                tile_pos_x = (tile_x - self.tile_offset_for_display_x) * self.tile_width
                curr_elem = self.board_for_display[tile_y][tile_x]
                self.canvas.blit(self.tiles[curr_elem], (tile_pos_x, tile_pos_y))



    def display_radar(self):
        self.canvas.blit(self.radar_surface, (self.radar_start_pos_x, self.radar_start_pos_y))

        # window frame in radar with outline width of 2 pixels
        outline_width = 2
        win_frame_x = self.radar_start_pos_x + self.window_loc_x * self.radar_tile_size_px - outline_width
        win_frame_y = self.radar_start_pos_y + self.window_loc_y * self.radar_tile_size_px - outline_width
        self.win_frame_width = self.window_num_of_tiles_x * self.radar_tile_size_px + 2 * outline_width
        self.win_frame_heigth = self.window_num_of_tiles_y * self.radar_tile_size_px + 2 * outline_width
        pygame.draw.rect(self.canvas, self.win_frame_color,
                         (win_frame_x, win_frame_y, self.win_frame_width, self.win_frame_heigth),
                         outline_width)

    def display_timeout_msg(self):
        timeout_font = pygame.font.SysFont("", 30)
        timeout_text = timeout_font.render('Timeout', True, (255, 0, 0))
        self.canvas.blit(timeout_text,
                         ((self.window_width - timeout_text.get_width()) // 2, self.delta_from_top_y +
                          (self.window_height - timeout_text.get_height()) // 2))

    def update_window_location(self, horizontal_displacement, vertical_displacement):
        # horizontal_displacement/vertical_displacement can be 1/-1 --> right/left, down/up
        # window location is in tiles, not pixels
        new_window_loc_x = self.window_loc_x + horizontal_displacement
        new_window_loc_y = self.window_loc_y + vertical_displacement
        if (new_window_loc_x >= 0) and (new_window_loc_x <= self.num_of_tiles_x - self.window_num_of_tiles_x):
            self.window_loc_x = new_window_loc_x
        if (new_window_loc_y >= 0) and (new_window_loc_y <= self.num_of_tiles_y - self.window_num_of_tiles_y):
            self.window_loc_y = new_window_loc_y

    def update_clock(self):
        if self.game_started and self.time < 999 and not self.game_over:
            # print(self.is_game_over())
            curr_time = time.time()
            time_from_start = int(curr_time - self.game_start_time)
            self.time = time_from_start

    def update_score(self, points_to_update):
        self.score += points_to_update

    def close_opened_mine_tile(self):
        self.hit_mine = False   # func is called when hit mine timeout has passed
        """self.shown_array[self.mine_loc_y][self.mine_loc_x] = self.HIDDEN
        self.board_for_display[self.mine_loc_y][self.mine_loc_x] = self.TILE_BLOCKED"""
        self.shown_array[self.mine_loc_y][self.mine_loc_x] = self.HIDDEN
        self.update_board_for_display(self.mine_loc_x, self.mine_loc_y)


    def is_mine(self, tile_x, tile_y, left_click, right_click):
        if left_click and not right_click and self.mines_array[tile_y][tile_x] == 1:
            self.mine_loc_x = tile_x
            self.mine_loc_y = tile_y
            return True
        else:
            return False

    def is_game_over(self):
        font = pygame.font.SysFont("", 40)
        """if self.hit_mine:
            self.game_over = True  # TODO: check if this is used, if not - remove
            lose_text = font.render("You lose", True, (255, 0, 0))
            self.canvas.blit(lose_text, ((self.canvas_pixel_width - lose_text.get_width()) // 2, self.canvas_pixel_height // 2))"""
        if (self.mines_array != np.zeros(self.board_shape, dtype=np.uint8)).all() and \
            (self.flags_array == self.mines_array).all():
            self.game_over = True  # TODO: check if this is used, if not - remove
            win_text = font.render("You win", True, (255, 0, 0))
            self.canvas.blit(win_text, ((self.canvas_pixel_width - win_text.get_width()) // 2, self.canvas_pixel_height // 2))
            if not self.win:
                self.win = True
                self.add_score = True

    def is_mouse_over_new_game_button(self, mouse_position):
        # function decides whether the mouse is located over the new game button
        new_game_button_x = (self.canvas_pixel_width - self.new_button_icon.get_width()) // 2
        new_game_button_y = 2
        new_game_button_width = new_game_button_x + self.new_button_icon.get_width()
        new_game_button_height = new_game_button_y + self.new_button_icon.get_height()
        if mouse_position[0] > new_game_button_x and mouse_position[0] < new_game_button_width:
            if mouse_position[1] > new_game_button_y and mouse_position[1] < new_game_button_height:
                return True
        else:
            return False # TODO: refactor

    def is_mouse_over_radar(self, mouse_position):
        return (mouse_position[0] >= self.radar_start_pos_x and
                mouse_position[0] <= self.radar_start_pos_x + self.radar_width and
                mouse_position[1] >= self.radar_start_pos_y and
                mouse_position[1] <= self.radar_start_pos_y + self.radar_height)

    def is_mouse_over_window(self, mouse_position):
        return (mouse_position[0] >= self.window_start_pos_x and
                mouse_position[0] <= self.window_start_pos_x + self.window_width and
                mouse_position[1] >= self.window_start_pos_y and
                mouse_position[1] <= self.window_start_pos_y + self.window_height)

    def radar_pixel_xy_to_new_window_loc(self, mouse_position):
        mouse_relative_pos_x = mouse_position[0] - self.radar_start_pos_x
        mouse_relative_pos_y = mouse_position[1] - self.radar_start_pos_y
        radar_tile_x = mouse_relative_pos_x // self.radar_tile_size_px
        radar_tile_y = mouse_relative_pos_y // self.radar_tile_size_px
        self.window_loc_x = min(self.num_of_tiles_x - self.window_num_of_tiles_x,
                                max(radar_tile_x - self.window_num_of_tiles_x//2, 0))
        #print("self.window_loc_x: ", self.window_loc_x)
        self.window_loc_y = min(self.num_of_tiles_y - self.window_num_of_tiles_y,
                                max(radar_tile_y - self.window_num_of_tiles_y//2, 0))
        #print("self.window_loc_y: ", self.window_loc_y)

