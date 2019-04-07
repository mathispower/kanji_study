#!/usr/bin/env python3
# coding: utf-8
version = "1.0"
###############################################################################
###                                                                         ###
###                               Dependencies                              ###
###                                                                         ###
###############################################################################
import argparse, datetime, json, os ,re, signal, sys, threading,time
import logging, logging.handlers, subprocess as sp
import cv2, numpy as np
from collections import deque

# User interface imports
from PIL import Image
from PIL import ImageTk

import tkinter as tk
from tkinter import filedialog as tkFileDialog
from tkinter import messagebox as tkMessageBox
from tkinter import font as tkFont

script_name = os.path.basename(__file__)[:-3]
DIR_CWD  = os.getcwd()
DIR_THIS = os.path.dirname(os.path.abspath(__file__))

DIR_DATA = os.path.join(DIR_THIS, "dicts")

WIN = "win" in sys.platform

if WIN:
    import winreg

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

###############################################################################
###                                                                         ###
###                        Global Lists/Dictionaries                        ###
###                                                                         ###
###############################################################################
colors = { # Matterport color scheme
           "Dark Blue":"#002F40",
           "Dark Yellow":"#FAAC17",
           "Light Gray":"#D1D3D4",
           "Medium Gray":"#989693",
           "Yellow":"#FBCD00",
           # Indicator disable/enabled colors
           "dis_grn":"#008B00", "en_grn":"#00EE00",
           "dis_red":"#8B0000", "en_red":"#FF0000",
           "dis_yel":"#8B8B00", "en_yel":"#FFFF00", }

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
        self.root.configure(background=colors["Medium Gray"])

        self.running  = True
        self.screen_h = self.root.winfo_screenheight()
        self.screen_w = self.root.winfo_screenwidth()
        self.win_h    = 1000 #self.screen_h - 80
        self.win_w    = 1800 #self.screen_w - 20

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
        self.cur_i = 0     # the current index of self.dict
        self.dict  = []    # the items not marked as correct
        self.show  = False # show the answer
        self.total = 0     # the total number of items in loaded dictionary

    def alert_error(self,msg):
        """ This will call the error_popup class that shows a popup with the
            message in red text. Continue execuation when popup is closed. """
        self.w = error_popup(self.root,msg)
        self.root.wait_window(self.w.top)

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
        self.f_top = tk.Frame(self.root, background=colors["Medium Gray"])
        self.f_top.pack(expand=1)

        #### LABELS
        self.f_status = tk.Frame(self.f_top, background=colors["Medium Gray"])
        self.f_status.pack()

        self.l_num = tk.Label( self.f_status, text='',
                               bg=self.f_top.master["bg"], width=20,
                               font=("Helvetica", 20) )
        self.l_num.pack(pady=20, side=tk.LEFT)

        self.l_met = tk.Label( self.f_status, text='',
                               bg=self.f_top.master["bg"], width=20,
                               font=("Helvetica", 20) )
        self.l_met.pack(pady=20, side=tk.LEFT)

        self.l_show = tk.Label( self.f_top, text='',
                                bg=self.f_top.master["bg"], width=20,
                                font=("Helvetica", 80) )
        self.l_show.pack(pady=20)

        self.l_ans = tk.Label( self.f_top, text='',
                               bg=self.f_top.master["bg"], width=20,
                               font=("Helvetica", 80) )
        self.l_ans.pack(pady=20)

        #### BUTTONS
        self.f_but = tk.Frame(self.f_top, background=colors["Medium Gray"])
        self.f_but.pack()

        self.b_next = tk.Button( self.f_but, text="Next", width=10,
                                 font=("Helvetica", 20),
                                 command=self.toggle_next )
        self.b_next.pack(padx=10, pady=10, side=tk.LEFT)

        self.b_show = tk.Button( self.f_but, text="Show", width=10,
                                 font=("Helvetica", 20),
                                 command=self.toggle_show )
        self.b_show.pack(padx=10, pady=10, side=tk.LEFT)

        self.b_cor = tk.Button( self.f_but, text="Right!", width=10,
                                font=("Helvetica", 20),
                                command=self.toggle_right )
        self.b_cor.pack(padx=10, pady=10, side=tk.LEFT)

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

    def select_file(self):
        self.file = tkFileDialog.askopenfilename( initialdir=DIR_DATA,
                                                  defaultextension="txt",
                                                  title="Select Dictionary" )

        self.dict = []
        if not self.file: return

        with open(self.file, "r", encoding="utf-8") as f:
            for line in f:
                self.dict.append(line.rstrip().split('\t'))

        self.cur_i = 0
        self.total = len(self.dict)

        self.update_labels()

    def toggle_next(self):
        if len(self.dict):
            self.cur_i += 1
            if self.cur_i >= len(self.dict): self.cur_i = 0

            self.update_labels()

    def toggle_right(self):
        if len(self.dict):
            del self.dict[self.cur_i]
            if self.cur_i >= len(self.dict): self.cur_i = 0
            self.updt = True
            
            self.update_labels()

    def toggle_show(self):
        self.show = not self.show

        if self.show and len(self.dict):
            self.l_ans["text"] = self.dict[self.cur_i][0]
        else:
            self.l_ans["text"] = ''

    def update_labels(self):
        if len(self.dict):
            per_done = (self.total - len(self.dict)) / float(self.total) * 100

            self.l_num["text"]  = "%i/%i"%(self.cur_i+1, len(self.dict))
            self.l_met["text"]  = "%.0f%%"%per_done
            self.l_show["text"] = self.dict[self.cur_i][1]

        else:
            self.l_num["text"]  = ''
            self.l_met["text"]  = ''
            self.l_show["text"] = ''

        self.show = False; self.l_ans["text"] = ''

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
