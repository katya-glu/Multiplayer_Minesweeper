import pickle
from tkinter import *
from tkinter import ttk

class HighScore:

    # Frame variables
    small_frame_index = 0
    medium_frame_index = 1
    large_frame_index = 2

    def __init__(self, order_high_to_low, score_lines_num, column_width, align_left, filename, scores_db = [[],[],[]]):
        self.order_high_to_low = order_high_to_low
        self.score_lines_num = score_lines_num
        self.column_width = column_width
        self.align_left = align_left
        self.filename = filename
        self.scores_db = scores_db

        # UI attributes
        self.font = "Calibri 28"
        self.rank_label_width = 2
        self.name_label_width = 10
        self.score_label_width = 4
        self.label_height = 1
        self.background_color = "black"
        self.foreground_color = "white"
        self.pad_value = 1
        self.window_open = False

        # name entered by user
        self.player_name = None

    def add_score_to_score_db(self, new_score, size_index):
        # function receives new_score in the form [name, score], inserts it into the score_db in the right order and
        # in the right size of board
        scores_db = self.scores_db[size_index]
        # add to empty list
        if not scores_db:
            scores_db.insert(0, new_score)
            return scores_db

        if self.order_high_to_low:
            # lowest score, add to end of list
            if new_score[-1] < scores_db[-1][-1]:
                scores_db.append(new_score)
                return scores_db

            # search for insertion location
            for i in range(len(scores_db)):
                curr_row = scores_db[i]
                if new_score[-1] >= curr_row[-1]:
                    scores_db.insert(i, new_score)
                    break
                else:
                    continue

        # list is ordered from low to high
        else:
            # highest score, add to end of list
            if new_score[-1] > scores_db[-1][-1]:
                scores_db.append(new_score)
                return scores_db

            # search for insertion location
            for i in range(len(scores_db)):
                curr_row = scores_db[i]
                if new_score[-1] <= curr_row[-1]:
                    scores_db.insert(i, new_score)
                    break
                else:
                    continue

        # score_lines_num is the max number of high score lines, an argument to the function
        if len(scores_db) > self.score_lines_num:
            scores_db.pop()

        return scores_db

    def print_scores(self, size_index):
        curr_score_db = self.scores_db[size_index]
        if not curr_score_db:
            print("Empty list")
            return

        score_string = ""
        for i in range(len(curr_score_db)):
            curr_row = curr_score_db[i]
            score_string += "{0:02d} |".format(i+1)
            for j in range(len(curr_row)):
                element = str(curr_row[j])
                element = element[:self.column_width[j]]   # truncate string according to column_width
                if self.align_left[j]:
                    score_string += str(element) + (self.column_width[j] - len(element))*" " + "|"
                else:
                    score_string += (self.column_width[j] - len(element)) * " " + element
            score_string += "\n"

        print(score_string)

    def prepare_high_scores_for_display(self, frame, frame_index):
        # display this if there are no high scores
        if not self.scores_db[frame_index]:
            empty_label = Label(frame, text="No high scores")
            empty_label.pack()

        for row in range(len(self.scores_db[frame_index])):
            curr_row = self.scores_db[frame_index][row]
            # RANK
            rank = "{0:02d}".format(row+1)
            rank_label = Label(frame, text=rank, bg=self.background_color, fg=self.foreground_color, font=self.font,
                               width=self.rank_label_width, height=self.label_height)
            rank_label.grid(row=row+1, column=0, padx=self.pad_value, pady=self.pad_value)

            for column in range(len(curr_row)):
                element = str(curr_row[column])
                if column == 0:
                    # NAME
                    name_label = Label(frame, text=str(element), bg=self.background_color, fg=self.foreground_color, font=self.font,
                                       width=self.name_label_width, height=self.label_height, anchor=W)
                    name_label.grid(row=row+1, column=column+1, sticky=W, padx=self.pad_value, pady=self.pad_value)
                else:
                    # SCORE
                    score_label = Label(frame, text=str(element), bg=self.background_color, fg=self.foreground_color, font=self.font,
                                        width=self.score_label_width, height=self.label_height, anchor=E)
                    score_label.grid(row=row+1, column=column+1, sticky=E, padx=self.pad_value, pady=self.pad_value)


    def display_high_scores_window(self): # TODO: add empty high scores string
        # function creates a list for display in Tkinter window
        self.window_open = True
        high_scores_window = Tk()
        high_scores_window.title("High scores")

        my_notebook = ttk.Notebook(high_scores_window)
        my_notebook.pack()

        small_frame = Frame(my_notebook)
        medium_frame = Frame(my_notebook)
        large_frame = Frame(my_notebook)

        small_frame.pack(fill="both", expand=1)
        medium_frame.pack(fill="both", expand=1)
        large_frame.pack(fill="both", expand=1)

        my_notebook.add(small_frame, text="Small")
        my_notebook.add(medium_frame, text="Medium")
        my_notebook.add(large_frame, text="Large")

        self.prepare_high_scores_for_display(small_frame, self.small_frame_index)
        self.prepare_high_scores_for_display(medium_frame, self.medium_frame_index)
        self.prepare_high_scores_for_display(large_frame, self.large_frame_index)

        def on_closing():
            self.window_open = False
            high_scores_window.destroy()

        high_scores_window.protocol("WM_DELETE_WINDOW", on_closing)
        high_scores_window.mainloop()

    def is_window_open(self):
        return self.window_open

    def get_user_name(self):
        # new window to get name for high scores
        name_req_window = Tk()
        player_name = Entry(name_req_window, width=50)
        player_name.pack()
        player_name.insert(0, "Enter your name: ")

        def get_user_name_str():
            self.player_name = player_name.get()
            name_req_window.destroy()

        get_user_name_button = Button(name_req_window, text="OK", command=get_user_name_str)
        get_user_name_button.pack()

        name_req_window.mainloop()

    # func saves score_db to file,score_db is a list of lists of lists
    def save_scores_to_file(self):
        with open(self.filename, "wb") as score_file:
            pickle.dump(self.scores_db, score_file)

    # func loads score_db from file as a correct data struct (list of lists of lists)
    def load_scores_from_file(self):
        with open(self.filename, "rb") as score_file:
            self.scores_db = pickle.load(score_file)
            return self.scores_db

    def add_new_high_score(self, score, size_index):
        self.load_scores_from_file()
        self.get_user_name()
        if self.player_name != None and self.player_name != "Enter your name: ":
            self.scores_db[size_index] = self.add_score_to_score_db([self.player_name, score], size_index)
            self.save_scores_to_file()
            self.display_high_scores_window()

