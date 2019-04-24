#!/usr/bin/env python3
# coding: utf-8
version = "1.0"
""" TODO:
        - 
"""
###############################################################################
###                                                                         ###
###                               Dependencies                              ###
###                                                                         ###
###############################################################################
import argparse, datetime, json, os ,re, signal, sys, threading,time
import logging, logging.handlers, random, subprocess as sp
from collections import deque

# User interface imports
import tkinter as tk
from tkinter import filedialog as tkFileDialog
from tkinter import messagebox as tkMessageBox
from tkinter import font as tkFont

script_name = os.path.basename(__file__)[:-3]
DIR_CWD  = os.getcwd()
DIR_THIS = os.path.dirname(os.path.abspath(__file__))

DIR_DATA = os.path.join(DIR_THIS, "dicts")

WIN = "win" in sys.platform

LOG_FILE = os.path.join(DIR_THIS,"%s.log"%script_name)
logger = logging.getLogger(script_name)
logger.setLevel(logging.DEBUG)
handler = logging.handlers.RotatingFileHandler(
                                  LOG_FILE, maxBytes=10000000, backupCount=10 )
logger.addHandler(handler)

###############################################################################
###                                                                         ###
###                             Global Variables                            ###
###                                                                         ###
###############################################################################
debug    = False
lock     = threading.Lock()
screen_h = 0
screen_w = 0
t_q      = deque()
verbose  = False

# Game specific
difficulty = 8 # 28

###############################################################################
###                                                                         ###
###                        Global Lists/Dictionaries                        ###
###                                                                         ###
###############################################################################
colors = { "Dark Blue":"#002F40",
           "Dark Yellow":"#FAAC17",
           "Light Gray":"#D1D3D4",
           "Medium Gray":"#989693",
           "Yellow":"#FBCD00",
           # Indicator disable/enabled colors
           "dis_grn":"#008B00", "en_grn":"#00EE00",
           "dis_red":"#8B0000", "en_red":"#FF0000",
           "dis_yel":"#8B8B00", "en_yel":"#FFFF00",
           # Colors in tk speak
           "done":"orange2",
           "kanji":"pink",
           "meaning":"SkyBlue1",
           "reading":"pale green",
           "total":"DarkSeaGreen1" }

# There are two possible states for the test:
#   0 - Test is ready to begin; State following a program reset
#   1 - Test is currently running or, if t_q is empty, has completed running
run_state = 1

if WIN:
    t_c = {   "cyan":'',
             "green":'',
              "none":'',
               "red":'',
            "yellow":'',
          }
else:
    t_c = {   "cyan":"\033[1;36m",
             "green":"\033[1;32m",
              "none":"\033[0m",
               "red":"\033[1;31m",
            "yellow":"\033[1;33m",
          }

top_err = {"status":False, "msg":''}

###############################################################################
###                                                                         ###
###                                 Classes                                 ###
###                                                                         ###
###############################################################################
class App(tk.Tk):
    def __init__(self):
        self.root = tk.Tk()
        self.root.wm_title("Kanji Test: v%s"%version)
        # self.root.configure(background=colors["Light Gray"])

        self.running  = True
        self.screen_h = self.root.winfo_screenheight()
        self.screen_w = self.root.winfo_screenwidth()
        self.win_h    = 1600 #self.screen_h - 80
        self.win_w    = 2200 #self.screen_w - 20

        offset_x = (self.screen_w - self.win_w) // 2
        offset_y = (self.screen_h - self.win_h) // 2
        
        # if not debug: self.root.attributes('-fullscreen', True)

        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        self.root.geometry( "{0}x{1}+{2}+{3}".format( self.win_w,
                                                      self.win_h,
                                                      offset_x,
                                                      offset_y ) )
        self.gen_widgets()

        global screen_h, screen_w
        screen_h = self.screen_h
        screen_w = self.screen_w

        self.file  = ''    # the dictionary file to load
        self.dict  = []    # the items not marked as correct
        self.options = []  # Scrambled list of answer options
        self.types = []    # what type each option is (meaning, char, reading)

        self.overflow = [] # if there are too many to display at once
        self.tally = {"done":0, "total":0}

        # Autoload first file
        self.select_file("dicts/Kanji01.txt")

    def alert_error(self,msg):
        """ This will call the error_popup class that shows a popup with the
            message in red text. Continue execuation when popup is closed. """
        self.w = error_popup(self.root,msg)
        self.root.wait_window(self.w.top)

    def create_puzzle(self):
        """
        -----------------------------------------------------------------------
        |          |         |                 f_choices                      |
        |          |         |------------------------------------------------|
        |  f_list  | f_space |                  f_space                       |
        |          |         |------------------------------------------------|
        |          |         |                   f_ans                        |
        -----------------------------------------------------------------------
        """
        self.f_top.destroy()

        self.f_top = tk.Frame(self.root)
        self.f_top.pack(expand=1)

        self.f_list = tk.Frame(self.f_top, padx=1, pady=1, bg="black")
        self.f_list.grid(column=0, row=0, rowspan=3)

        f_space = tk.Frame(self.f_top, width=10)
        f_space.grid(column=1, row=0, rowspan=3)

        self.options = [self.dict[i][0] for i in range(len(self.dict))]

        height = 1; width = 12
        self.list = {}
        total_text = "%i/%i"%(self.tally["done"], self.tally["total"])
        self.list["total"] = tk.Label( self.f_list,
                                       text=total_text,
                                       height=height, width=width,
                                       background="thistle1",
                                       font=("Helvetica", 20) )
        self.list["total"].pack(pady=1, fill=tk.X)

        self.list["tally"] = tk.Label( self.f_list,
                                       text="0/%i"%len(self.options),
                                       height=height, width=width,
                                       background="thistle1",
                                       font=("Helvetica", 20) )
        self.list["tally"].pack(pady=1, fill=tk.X)

        for o in self.options:
            self.list[o] = tk.Label( self.f_list, text=o,
                                     # text='',
                                     height=1, width=10,
                                     background="white",
                                     font=("Helvetica", 20) )
            self.list[o].pack(pady=1, fill=tk.X)

        self.f_choices = tk.Frame(self.f_top, padx=1, pady=1, bg="black")
        self.f_choices.grid(column=2, row=0)

        self.options.extend([self.dict[i][1] for i in range(len(self.dict))])
        self.options.extend([self.dict[i][2] for i in range(len(self.dict))])
        random.shuffle(self.options)

        self.types = ['' for i in range(len(self.options))]
        for i in range(len(self.types)):
            text = self.options[i]
            letter = [ord(text[j]) for j in range(len(text))]
            self.types[i] = "reading"
            for l in letter:
                if l <= 255: self.types[i] = "meaning"; break
                elif l >= 0x4E00: self.types[i] = "kanji"; break

        num_elements = len(self.options)
        self.choices = {}; self.selects = [0 for i in range(num_elements)]
        num_cols = 4
        for i in range(num_elements):
            row = int(i / num_cols)
            col = int(i % num_cols)
            if self.types[i] == "meaning": font_size = 20
            elif self.types[i] == "reading": font_size = 30
            elif self.types[i] == "kanji": font_size = 40

            self.choices[i] = tk.Label( self.f_choices, text=self.options[i],
                                        height=height, width=width,
                                        background="white",
                                        font=("Helvetica", font_size) )
            self.choices[i].grid( column=col, row=row, padx=2, pady=2,
                                  sticky="nsew" )

            self.choices[i].bind("<ButtonPress-1>", self.select)

        col += 1
        if col != 0:
            for i in range(num_cols - col):
                t0 = tk.Label( self.f_choices, text='',
                               height=height, width=width )
                t0.grid(column=col+i, row=row, padx=2, pady=2, sticky="nsew")

        f_space = tk.Frame(self.f_top, height=10)
        f_space.grid(column=2, row=1)

        self.f_ans = tk.Frame(self.f_top, padx=1, pady=2, bg="black")
        self.f_ans.grid(column=2, row=2)

        self.l_kanj = tk.Label( self.f_ans, text="漢字",
                                font=("Helvetica", 40),
                                height=height, width=width,
                                background="pink" )
        self.l_kanj.pack(side=tk.LEFT, padx=1, fill=tk.BOTH)

        self.l_read = tk.Label( self.f_ans, text="Reading",
                                font=("Helvetica", 30),
                                height=height, width=width,
                                background="pale green" )
        self.l_read.pack(side=tk.LEFT, padx=1, fill=tk.BOTH)

        self.l_mean = tk.Label( self.f_ans, text="Meaning",
                                font=("Helvetica", 30),
                                height=height, width=width,
                                background="SkyBlue1" )
        self.l_mean.pack(side=tk.LEFT, padx=1, fill=tk.BOTH)

        self.ans_boxes = { "kanji":[self.l_kanj, "漢字"],
                           "meaning":[self.l_mean, "Meaning"],
                           "reading":[self.l_read, "Reading"] }

        # self.b_cor = tk.Button( self.f_but, text="Right!", width=10,
        #                         font=("Helvetica", 20),
        #                         command=self.toggle_right )
        # self.b_cor.pack(padx=10, pady=10, side=tk.LEFT)

    def gen_widgets(self):
        """
        =========================== root.geometry =============================
        |                                                                     |
        | ============================= f_top ==============================  |
        | |                                                                 | |

        | =================================================================== |
        =======================================================================
        b = button         c = column number
        c = canvas         r = row number
        f = frame          w = pointer to widget
        i = indicator      x = left/right position
        l = label          y = up/down position
        n = font
        t = text
        """
        self.buttons = []
        self.wids = {}

        # Fonts
        self.n_test_b = tkFont.Font( family='Helvetica', size=48,
                                    weight=tkFont.BOLD )

        # Top Level Frame to center in window
        self.f_top = tk.Frame(self.root)
        self.f_top.pack(expand=1)

        #### MENU
        self.menu_bar = tk.Menu(self.root)

        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.file_menu.add_command(label="Load", command=self.select_file)
        self.file_menu.add_command(label="Exit", command=self.quit)
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)
        self.root.config(menu=self.menu_bar)

    def quit(self):
        """ End the application. """
        global t_q
        t_q.clear()
        self.running = False

        Quit()

    def refresh(self):
        self.root.update_idletasks()
        self.root.update()

    def reset(self):
        # reset button
        self.reset_buttons()

    def reset_buttons(self):
        return

    def run(self):
        """  """
        global run_state, t_q

        # Make sure the main app window shows before any other (like errors)
        self.refresh()

        # Start the main application loop which will run until the script ends
        while self.running:

            self.refresh()

        Quit()

    def select(self, event):
        val = event.widget.cget("text")
        i = 0
        for n in self.options:
            if n == val: break
            i += 1

        # index = int(event.widget.cget("text").split(' ')[-1]) - 1
        off = not self.selects[i]

        self.select_clear(self.types[i])

        if off:
            if self.types[i] == "meaning": color = colors["meaning"]
            elif self.types[i] == "reading": color = colors["reading"]
            else: color = colors["kanji"]
            self.choices[i].configure(bg=color)
            self.selects[i] = 1

            self.ans_boxes[self.types[i]][0].configure(text=val)

        # Check for success
        on = [i for i in range(len(self.selects)) if self.selects[i]]
        if len(on) == 3:
            poss = {}
            for i in range(3):
                poss[self.types[on[i]]] = self.options[on[i]]

            success = 0
            for i in range(len(self.dict)):
                if self.dict[i][0] == poss["kanji"]:
                    success += 1
                    if self.dict[i][2] == poss["meaning"]: success += 1
                    if self.dict[i][1] == poss["reading"]: success += 1
                    break

            if success == 3:
                for key in self.list:
                    if poss["kanji"] == key:
                        self.list[key].configure(text="✓ %s"%key)
                        if self.list[key].cget("bg") != colors["done"]:
                            self.cur_done += 1
                            self.tally["done"] += 1
                            self.list[key].configure(bg=colors["done"])
                            new_tally = "%i/%i" % ( self.cur_done,
                                                    len(self.list)-1 )
                            self.list["tally"].configure(text=new_tally)

                            new_total = "%i/%i" % ( self.tally["done"],
                                                    self.tally["total"] )
                            self.list["total"].configure(text=new_total)
                        break

                self.select_clear("ALL")

                if self.cur_done == self.all_done:
                    if len(self.overflow) > 0:
                        self.dict = self.overflow
                        self.overflow = []

                        if len(self.dict) > difficulty:
                            self.overflow = self.dict[difficulty:]
                            self.dict = self.dict[:difficulty]

                        self.all_done = len(self.dict)
                        self.cur_done = 0

                        self.create_puzzle()

                    else:
                        self.f_top.destroy()
                        w = message_popup(self.root,"DONE!")
                        self.root.wait_window(w.top)

    def select_clear(self, t_type):
        for i in range(len(self.selects)):
            if t_type == "ALL" or self.types[i] == t_type:
                if self.selects[i]:
                    self.choices[i].configure(bg="white")
                    self.selects[i] = 0

                    self.ans_boxes[self.types[i]][0].configure(text= \
                        self.ans_boxes[self.types[i]][1])

    def select_file(self, file_path=None):
        self.file = file_path
        if not self.file:
            self.file = tkFileDialog.askopenfilename( \
                initialdir=DIR_DATA, defaultextension="txt",
                title="Select Dictionary" )

        self.dict = []
        if not self.file: return

        with open(self.file, "r", encoding="utf-8") as f:
            for line in f:
                self.dict.append(line.rstrip().split('\t'))

        if len(self.dict[0]) < 3:
            return

        self.tally["done"] = 0
        self.tally["total"] = len(self.dict)

        random.shuffle(self.dict)

        if len(self.dict) > difficulty:
            self.overflow = self.dict[difficulty:]
            self.dict = self.dict[:difficulty]

        self.all_done = len(self.dict)
        self.cur_done = 0

        self.create_puzzle()

class error_popup(object):
    def __init__(self, caller, err_msg):
        self.top = tk.Toplevel(caller)

        self.top.resizable(0,0)
        self.top.focus_force()

        # Center window
        width    = len(err_msg) * 15
        height   = 75
        offset_x = ( screen_w - width  ) // 2
        offset_y = ( screen_h - height ) // 2
        self.top.geometry( "{0}x{1}+{2}+{3}".format( width, height,
                                                     offset_x, offset_y ) )

        self.lbl = tk.Label( self.top, text=err_msg, font='Helvetica 18 bold',
                             fg="red" )
        self.lbl.pack()
        self.btn = tk.Button(self.top, text="OK", command=self.done)
        self.btn.bind('<Return>',self.done)
        self.btn.focus_force()
        self.btn.pack()

    def done(self,event=None):
        self.top.destroy()

class message_popup(object):
    def __init__(self, caller, msg):
        self.top = tk.Toplevel(caller)

        self.top.resizable(0,0)
        self.top.focus_force()

        # Center window
        width    = len(msg) * 20
        height   = 75
        offset_x = ( screen_w - width  ) // 2
        offset_y = ( screen_h - height ) // 2
        self.top.geometry( "{0}x{1}+{2}+{3}".format( width, height,
                                                     offset_x, offset_y ) )

        self.lbl = tk.Label(self.top, text=msg, font='Helvetica 18 bold')
        self.lbl.pack()
        self.btn = tk.Button(self.top, text="OK", command=self.done)
        self.btn.bind('<Return>',self.done)
        self.btn.focus_force()
        self.btn.pack()

    def done(self,event=None):
        self.top.destroy()

###############################################################################
###                                                                         ###
###                                Functions                                ###
###                                                                         ###
###############################################################################
def add_thread(func,args=None,thread=False,side="right"):
    global t_q

    if thread:
        if side == "right":
            t_q.append({"thread":threading.Thread(target=func,
                                                  kwargs=args,
                                                  name=func.__name__),
                        "started":False})
        else:
            t_q.appendleft({"thread":threading.Thread(target=func,
                                                      kwargs=args,
                                                      name=func.__name__),
                            "started":False})
    else:
        if side == "right":
            t_q.append({"thread":[func,args],"started":False})
        else:
            t_q.appendleft({"thread":[func,args],"started":False})

def ArgParser():
    """ This function will handle the input arguments while keeping the main
        function tidy. """

    usage = """
    general_tools.py [FLAGS]
    
            """

    parser = argparse.ArgumentParser( description = "Description",
                                      usage = usage)

    parser.add_argument( "--debug",
                         action  = "store_const",
                         const   = True,
                         default = False,
                         dest    = "debug",
                         help    = "Run in debug mode." )

    parser.add_argument( "-v",
                         action  = "store_const",
                         const   = True,
                         default = False,
                         dest    = "verbose",
                         help    = "Make this script a chatterbox." )

    args = parser.parse_args()

    global debug, verbose
    debug   = args.debug
    verbose = args.verbose

def call_external(args,error='',env=os.environ):
    msg = "Calling external: %r" % args
    log(msg,log_type="info")

    p = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT, env=env)

    with lock:
        top_err["msg"] = ''

    output = []
    while True:
        line = p.stdout.readline().rstrip()
        if len(line) > 2:
            output.append(line)
            log("stdout: %s"%line,log_type="info")

        with lock:
            if len(error) > 0:
                if type(error) is not list: error = [error]
                checks = []
                for e in error:
                    checks.append(line.find(e) >= 0)
                if np.all(checks): top_error["msg"] = line

        if not line: break

    return '_'.join(output)

def get_time_stamp():
    t0   = datetime.datetime.now()
    day  = int(t0.strftime("%d"))
    hour = int(t0.strftime("%H"))

    if day < 10: day = "0%i" % day
    else:day = "%i" % day

    if hour < 10: hour = "0%i" % hour
    else: hour = "%i" % hour

    t_stamp = t0.strftime("%Y%m") + day + "_%s" % hour + t0.strftime("%M%S")

    return t_stamp

def log(message, custom_msg='', log_type="warning", color=t_c["none"]):
    log_text = "[%s] %s" % (get_time_stamp(), message)
    if custom_msg != '': log_text += ":%s"%custom_msg

    if log_type == "critical":
        color = t_c["red"]
        log_text = "[critical] %s" % log_text
        logger.critical(log_text)

    elif log_type == "info":
        if debug: color = t_c["cyan"]
        else: color = t_c["none"]
        log_text = "[info] %s" % log_text
        logger.info(log_text)

    elif log_type == "error":
        color = t_c["red"]
        log_text = "[error] %s" % log_text
        logger.error(log_text)

    elif log_type == "warning":
        color = t_c["yellow"];
        log_text = "[warning] %s" % log_text
        logger.warning(log_text)

    elif log_type == "debug":
        color = t_c["cyan"]
        log_text = "[debug] %s" % log_text
        logger.debug(log_text)

    else:
        # if debug: color = t_c["cyan"]
        # else: color = t_c["none"]
        log_text = "[other] %s" % log_text
        logger.info(log_text)

    if verbose:
        print("%s%s%s"%(color,log_text,t_c["none"]));sys.stdout.flush()

def Quit(signal=signal.SIGINT, frame=None):
    log("Exiting",log_type="info")

    sys.exit(0)

def reset():
    global top_err

    ui.reset()

if __name__ == "__main__":
    # Catch Ctrl-C
    signal.signal(signal.SIGINT, Quit)

    log("Starting program: v%s"%version,log_type="info")

    ArgParser()

    log("Starting App",sys._getframe().f_code.co_name,log_type="info")
    ui = App()
    ui.run()

    Quit()
