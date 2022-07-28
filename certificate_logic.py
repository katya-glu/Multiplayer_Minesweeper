from tkinter import *

def is_valid_certificate(cert_str):
    return cert_str.isdigit()  # TODO: add function to parse cert

def show_certificate_code(self, game_board):
    certificate_window = Tk()
    certificate_window.title("Certificate")
    certificate_code = "{},{},{}".format(str(game_board.score), self.seed_str, self.player_name)
    certificate_label = Label(certificate_window, text=certificate_code)
    certificate_label.pack()
    certificate_window.mainloop()


# TODO: create function that receives entered seed and transforms to secret seed