from tkinter import *
import numpy as np


def is_valid_certificate(cert_str):
    return cert_str.isdigit()  # TODO: add function to parse cert


def show_certificate_code(game_board, seed_str, player_name):   # TODO: add certificate encryption
    # opens new window, displays in window
    certificate_window = Tk()
    certificate_window.title("Certificate")
    certificate_code = "{},{},{}".format(str(game_board.score), seed_str, player_name)
    certificate_label = Label(certificate_window, text=certificate_code)
    certificate_label.pack()
    certificate_window.mainloop()


def calc_secret_key(game_number):
    return game_number


def set_random_seed(game_number):
    secret_key = calc_secret_key(game_number)
    np.random.seed(secret_key)  # random_seed generates a specific board setup for all users who enter this game_number


# TODO: replace with actual logic and never push to git