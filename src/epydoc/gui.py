#!/usr/bin/env python
#
# objdoc: epydoc command-line interface
# Edward Loper
#
# Created [03/15/02 10:31 PM]
# $Id$
#

"""
Graphical interface to epydoc.  This interface might be useful for
systems where it's inconvenient to use the command-line interface
(such as Windows).  It supports all of the features that are supported
by the command-line interface.  It also supports loading and saving of
X{project files}, which store a set of related modules, and the
options that should be used to generate the documentation for those
modules.

Note: I put this together in an afternoon, so it might not be as
clean and reliable as the other epydoc modules.

Any command line arguments ending in C{.prj} will be loaded as project
files; any other command line arguments will be added as modules (if
possible).  
"""

from Tkinter import *
from tkFileDialog import askopenfilename, asksaveasfilename
from thread import start_new_thread, exit_thread
from pickle import dump, load
import sys

from epydoc.css import STYLESHEETS
from epydoc.cli import _find_modules
from epydoc.html import HTMLFormatter
from epydoc.objdoc import DocMap

##/////////////////////////////////////////////////////////////////////////
## CONSTANTS
##/////////////////////////////////////////////////////////////////////////

DEBUG = 0

# Colors for tkinter display
BG_COLOR='#90a0b0'
ACTIVEBG_COLOR='#8090a0'
TEXT_COLOR='black'
ENTRY_COLOR='#506080'
COLOR_CONFIG = {'background':BG_COLOR, 'highlightcolor': BG_COLOR,
                'foreground':TEXT_COLOR, 'highlightbackground': BG_COLOR}
SB_CONFIG = {'troughcolor':BG_COLOR, 'activebackground':BG_COLOR,
             'background':BG_COLOR, 'highlightbackground':BG_COLOR}
LISTBOX_CONFIG = {'highlightcolor': BG_COLOR, 'highlightbackground': BG_COLOR,
                  'foreground':TEXT_COLOR, 'selectforeground': TEXT_COLOR,
                  'selectbackground': ACTIVEBG_COLOR, 'background':BG_COLOR}
BUTTON_CONFIG = {'background':BG_COLOR, 'highlightthickness':0, 'padx':4, 
                 'highlightbackground': BG_COLOR, 'foreground':TEXT_COLOR,
                 'highlightcolor': BG_COLOR, 'activeforeground': TEXT_COLOR,
                 'activebackground': ACTIVEBG_COLOR, 'pady':0}

# Colors for the progress bar
PROGRESS_HEIGHT = 16
PROGRESS_WIDTH = 200
PROGRESS_BG='#305060'
PROGRESS_COLOR1 = '#30c070'
PROGRESS_COLOR2 = '#60ffa0'
PROGRESS_COLOR3 = '#106030'

# On tkinter canvases, where's the zero coordinate?
if sys.platform.lower().startswith('win'):
    DX = 3; DY = 3
    DH = 0; DW = 7
else:
    DX = 1; DY = 1
    DH = 1; DW = 3

# How much of the progress is building the docs? (0-1)
BUILD_PROGRESS = 0.3
WRITE_PROGRESS = 1.0 - BUILD_PROGRESS

##/////////////////////////////////////////////////////////////////////////
## IMAGE CONSTANTS
##/////////////////////////////////////////////////////////////////////////

LEFT_GIF='''\
R0lGODlhDAALAPcAAAAAAAAAMwAAZgAAmQAAzAAA/zMAADMAMzMAZjMAmTMAzDMA/2YAAGYAM2YA
ZmYAmWYAzGYA/5kAAJkAM5kAZpkAmZkAzJkA/8wAAMwAM8wAZswAmcwAzMwA//8AAP8AM/8AZv8A
mf8AzP8A/wAzAAAzMwAzZgAzmQAzzAAz/zMzADMzMzMzZjMzmTMzzDMz/2YzAGYzM2YzZmYzmWYz
zGYz/5kzAJkzM5kzZpkzmZkzzJkz/8wzAMwzM8wzZswzmcwzzMwz//8zAP8zM/8zZv8zmf8zzP8z
/wBmAABmMwBmZgBmmQBmzABm/zNmADNmMzNmZjNmmTNmzDNm/2ZmAGZmM2ZmZmZmmWZmzGZm/5lm
AJlmM5lmZplmmZlmzJlm/8xmAMxmM8xmZsxmmcxmzMxm//9mAP9mM/9mZv9mmf9mzP9m/wCZAACZ
MwCZZgCZmQCZzACZ/zOZADOZMzOZZjOZmTOZzDOZ/2aZAGaZM2aZZmaZmWaZzGaZ/5mZAJmZM5mZ
ZpmZmZmZzJmZ/8yZAMyZM8yZZsyZmcyZzMyZ//+ZAP+ZM/+ZZv+Zmf+ZzP+Z/wDMAADMMwDMZgDM
mQDMzADM/zPMADPMMzPMZjPMmTPMzDPM/2bMAGbMM2bMZmbMmWbMzGbM/5nMAJnMM5nMZpnMmZnM
zJnM/8zMAMzMM8zMZszMmczMzMzM///MAP/MM//MZv/Mmf/MzP/M/wD/AAD/MwD/ZgD/mQD/zAD/
/zP/ADP/MzP/ZjP/mTP/zDP//2b/AGb/M2b/Zmb/mWb/zGb//5n/AJn/M5n/Zpn/mZn/zJn//8z/
AMz/M8z/Zsz/mcz/zMz/////AP//M///Zv//mf//zP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACH5BAEAANcALAAAAAAMAAsA
AAg6AK8JHEhw0iSCBSe5UYLwmsGFShgOfBgx4kSFFStecwMxo0aBAEqU8ChxYMiRHxGeTKlSZMmG
10IGBAA7
'''

RIGHT_GIF='''\
R0lGODlhDAALAPcAAAAAAAAAMwAAZgAAmQAAzAAA/zMAADMAMzMAZjMAmTMAzDMA/2YAAGYAM2YA
ZmYAmWYAzGYA/5kAAJkAM5kAZpkAmZkAzJkA/8wAAMwAM8wAZswAmcwAzMwA//8AAP8AM/8AZv8A
mf8AzP8A/wAzAAAzMwAzZgAzmQAzzAAz/zMzADMzMzMzZjMzmTMzzDMz/2YzAGYzM2YzZmYzmWYz
zGYz/5kzAJkzM5kzZpkzmZkzzJkz/8wzAMwzM8wzZswzmcwzzMwz//8zAP8zM/8zZv8zmf8zzP8z
/wBmAABmMwBmZgBmmQBmzABm/zNmADNmMzNmZjNmmTNmzDNm/2ZmAGZmM2ZmZmZmmWZmzGZm/5lm
AJlmM5lmZplmmZlmzJlm/8xmAMxmM8xmZsxmmcxmzMxm//9mAP9mM/9mZv9mmf9mzP9m/wCZAACZ
MwCZZgCZmQCZzACZ/zOZADOZMzOZZjOZmTOZzDOZ/2aZAGaZM2aZZmaZmWaZzGaZ/5mZAJmZM5mZ
ZpmZmZmZzJmZ/8yZAMyZM8yZZsyZmcyZzMyZ//+ZAP+ZM/+ZZv+Zmf+ZzP+Z/wDMAADMMwDMZgDM
mQDMzADM/zPMADPMMzPMZjPMmTPMzDPM/2bMAGbMM2bMZmbMmWbMzGbM/5nMAJnMM5nMZpnMmZnM
zJnM/8zMAMzMM8zMZszMmczMzMzM///MAP/MM//MZv/Mmf/MzP/M/wD/AAD/MwD/ZgD/mQD/zAD/
/zP/ADP/MzP/ZjP/mTP/zDP//2b/AGb/M2b/Zmb/mWb/zGb//5n/AJn/M5n/Zpn/mZn/zJn//8z/
AMz/M8z/Zsz/mcz/zMz/////AP//M///Zv//mf//zP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACH5BAEAANcALAAAAAAMAAsA
AAg5ACdNukawoEElbgQaPKgEocKF1xo2TDiQoUSHFSNevOjGjcaLJUoAKAhSpMWQIxcqQQmRoMmW
BAMCADs=
'''

##/////////////////////////////////////////////////////////////////////////
## THREADED DOCUMENTER
##/////////////////////////////////////////////////////////////////////////

def document(modules, options, progress, cancel):
    """
    Create the documentation for C{modules}, using the options
    specified by C{options}.  C{document} is designed to be started in
    its own thread by L{EpydocGUI._go}.

    @param options: The options to use for generating documentation.
        This includes keyword options that can be given to
        L{html.HTMLFormatter}, as well as the option C{outdir}, which
        controls where the output is written to.
    @type options: C{dictionary}
    @param progress: This first element of this list will be modified
        by C{document} to reflect its progress.  This first element
        will be a number between 0 and 1 while C{document} is creating
        the documentation; and the string C{"done"} once it finishes
        creating the documentation.
    @type progress: C{list}
    """
    
    # Create the documentation map.
    d = DocMap()

    # Build the documentation.
    progress[0] = 0.02
    for module in modules:
        if cancel[0]:
            progress[0] = 'cancel'
            exit_thread()
        d.add(module)
        progress[0] += (BUILD_PROGRESS*0.98)/len(modules)

    htmldoc = HTMLFormatter(d, **options)
    numfiles = htmldoc.num_files()

    # Set up the progress callback.
    def progress_callback(f, d, numfiles=numfiles,
                          progress=progress, cancel=cancel):
        if cancel[0]:
            progress[0] = 'cancel'
            exit_thread()
        if DEBUG: print 'documenting', f, d
        progress[0] += (WRITE_PROGRESS*0.98)/numfiles

    # Write the documentation.
    htmldoc.write(options.get('outdir', 'html'), progress_callback)

    # We're done.
    progress[0] = 'done'

##/////////////////////////////////////////////////////////////////////////
## GUI
##/////////////////////////////////////////////////////////////////////////

class EpydocGUI:
    """
    A graphical user interace to epydoc.
    """
    def __init__(self):
        self._afterid = 0
        self._modules = []
        self._progress = [None]
        self._cancel = [0]
        self._filename = None

        # Create the main window.
        self._top = Tk()
        self._top['background']=BG_COLOR
        self._top.bind('<Control-q>', self.destroy)
        self._top.bind('<Control-x>', self.destroy)
        self._top.bind('<Control-d>', self.destroy)
        self._top.title('Epydoc')
        self._topframe = Frame(self._top, background=BG_COLOR,
                               border=2, relief='raised')
        self._topframe.pack(expand=1, fill='both', padx=2, pady=2)
                            
        mainframe = Frame(self._topframe, background=BG_COLOR)
        mainframe.pack(expand=1, fill='both', side='left')

        # Initialize all the frames, etc.
        self._init_menubar()
        self._init_options(mainframe)
        self._init_progress_bar(mainframe)
        self._init_module_list(mainframe)
        self._init_bindings()

    def _init_menubar(self):
        menubar = Menu(self._top, borderwidth=2,
                       background=BG_COLOR,
                       activebackground=BG_COLOR)
        filemenu = Menu(menubar, tearoff=0)
        filemenu.add_command(label='Open Project', underline=0,
                             command=self._open,
                             accelerator='Ctrl-o')
        filemenu.add_command(label='Save Project', underline=0,
                             command=self._save,
                             accelerator='Ctrl-s')
        filemenu.add_command(label='Save As..', underline=5,
                             command=self._saveas,
                             accelerator='Ctrl-a')
        filemenu.add_separator()
        filemenu.add_command(label='Exit', underline=1,
                             command=self.destroy,
                             accelerator='Ctrl-x')
        menubar.add_cascade(label='File', underline=0, menu=filemenu)
        gomenu = Menu(menubar, tearoff=0)
        gomenu.add_command(label='Run Epydoc',  command=self._open,
                           underline=0, accelerator='Alt-g')
        menubar.add_cascade(label='Run', menu=gomenu, underline=0)
        self._top.config(menu=menubar)
        
    def _init_module_list(self, mainframe):
        mframe1 = Frame(mainframe, relief='groove', border=2,
                        background=BG_COLOR)
        mframe1.pack(side="top", fill='both', expand=1, padx=4, pady=3)
        l = Label(mframe1, text="Modules to document:",
                  justify='left', **COLOR_CONFIG) 
        l.pack(side='top', fill='none', anchor='nw', expand=0)
        mframe2 = Frame(mframe1, background=BG_COLOR)
        mframe2.pack(side="top", fill='both', expand=1)
        mframe3 = Frame(mframe1, background=BG_COLOR)
        mframe3.pack(side="bottom", fill='x', expand=0)
        self._module_list = Listbox(mframe2, **LISTBOX_CONFIG)
        self._module_list.pack(side="left", fill='both', expand=1)
        self._module_scroll = Scrollbar(mframe2, orient='vertical',
                                        **SB_CONFIG)
        self._module_scroll.config(command=self._module_list.yview)
        self._module_scroll.pack(side='right', fill='y')
        self._module_list.config(yscrollcommand=self._module_scroll.set)
        Label(mframe3, text="Add:", **COLOR_CONFIG).pack(side='left')
        self._module_entry = Entry(mframe3, **COLOR_CONFIG)
        self._module_entry.pack(side='left', fill='x', expand=1)
        self._module_entry.bind('<Return>', self._entry_module)
        self._module_browse = Button(mframe3, text="Browse",
                                     command=self._browse_module,
                                     **BUTTON_CONFIG) 
        self._module_browse.pack(side='right', expand=0, padx=2)
        
    def _init_progress_bar(self, mainframe):
        pframe1 = Frame(mainframe, background=BG_COLOR)
        pframe1.pack(side="bottom", fill='x', expand=0)
        self._go_button = Button(pframe1, width=4, text='Go!',
                                 underline=0, command=self._go,
                                 **BUTTON_CONFIG)
        self._go_button.pack(side='left', padx=4)
        pframe2 = Frame(pframe1, relief='groove', border=2,
                        background=BG_COLOR) 
        pframe2.pack(side="top", fill='x', expand=1, padx=4, pady=3)
        Label(pframe2, text='Progress:', **COLOR_CONFIG).pack(side='left')
        H = self._H = PROGRESS_HEIGHT
        W = self._W = PROGRESS_WIDTH
        c = self._canvas = Canvas(pframe2, height=H+DH, width=W+DW, 
                                  background=PROGRESS_BG, border=0,
                                  selectborderwidth=0, relief='sunken',
                                  insertwidth=0, insertborderwidth=0,
                                  highlightbackground=BG_COLOR)
        self._canvas.pack(side='left', fill='x', expand=1, padx=4)
        self._r2 = c.create_rectangle(0,0,0,0, outline=PROGRESS_COLOR2)
        self._r3 = c.create_rectangle(0,0,0,0, outline=PROGRESS_COLOR3)
        self._r1 = c.create_rectangle(0,0,0,0, fill=PROGRESS_COLOR1,
                                      outline='')
        self._canvas.bind('<Configure>', self._configure)

    def _configure(self, event):
        self._W = event.width-DW

    def _init_options(self, mainframe):
        self._leftImage=PhotoImage(master=self._top, data=LEFT_GIF)
        self._rightImage=PhotoImage(master=self._top, data=RIGHT_GIF)

        # Set up the options control frame
        oframe1 = Frame(mainframe, background=BG_COLOR)
        oframe1.pack(side="bottom", fill='x', expand=0)
        b1 = Button(oframe1, text="Options", justify='center',
                    border=0, relief='flat',
                    command=self._options_toggle, padx=2,
                    underline=0, pady=0, highlightthickness=0,
                    activebackground=BG_COLOR, **COLOR_CONFIG) 
        b2 = Button(oframe1, image=self._rightImage, relief='flat', 
                    border=0, command=self._options_toggle,
                    activebackground=BG_COLOR, **COLOR_CONFIG) 
        self._option_button = b2
        self._options_visible = 0
        b2.pack(side="right")
        b1.pack(side="right")

        # Set up the options frame
        oframe2 = Frame(self._topframe, relief='groove', border=2,
                        background=BG_COLOR)
        self._option_frame = oframe2
        l2 = Label(oframe2, text="Project Name:", **COLOR_CONFIG)
        l2.grid(row=2, col=0, columnspan=2, sticky='e')
        l3 = Label(oframe2, text="Project URL:", **COLOR_CONFIG)
        l3.grid(row=3, col=0, columnspan=2, sticky='e')
        l4 = Label(oframe2, text="Output Directory:", **COLOR_CONFIG)
        l4.grid(row=4, col=0, columnspan=2, sticky='e')
        l5 = Label(oframe2, text="CSS Stylesheet:", **COLOR_CONFIG)
        l5.grid(row=5, col=0, columnspan=2, sticky='e')
        self._name_entry = Entry(oframe2, **COLOR_CONFIG)
        self._name_entry.grid(row=2, col=2, sticky='ew', columnspan=2)
        self._url_entry = Entry(oframe2, **COLOR_CONFIG)
        self._url_entry.grid(row=3, col=2, sticky='ew', columnspan=2)
        self._out_entry = Entry(oframe2, **COLOR_CONFIG)
        self._out_entry.grid(row=4, col=2, sticky='ew')
        self._out_browse = Button(oframe2, text="Browse",
                                  command=self._browse_out,
                                  **BUTTON_CONFIG) 
        self._out_browse.grid(row=4, col=3, sticky='ew', padx=2)
        self._out_entry.insert(0, 'html')

        items = STYLESHEETS.items()
        def _css_sort(css1, css2):
            if css1[0] == 'default': return -1
            elif css2[0] == 'default': return 1
            else: return cmp(css1[0], css2[0])
        items.sort(_css_sort)
            
        i = 6
        css_var = self._css_var = StringVar(self._top)
        css_var.set('default')
        for (name, (sheet, descr)) in items:
            b = Radiobutton(oframe2, text=name, var=css_var, 
                            value=name, selectcolor='#208070',
                            **BUTTON_CONFIG)
            b.grid(row=i, col=1, sticky='w')
            l = Label(oframe2, text=descr, **COLOR_CONFIG)
            l.grid(row=i, col=2, columnspan=2, sticky='w')
            i += 1

        b = Radiobutton(oframe2, text='Select File', var=css_var, 
                        value='-other-', selectcolor='#208080',
                        **BUTTON_CONFIG)
        b.grid(row=i, col=1, sticky='w')
        self._css_entry = Entry(oframe2, **COLOR_CONFIG)
        self._css_entry.grid(row=i, col=2, sticky='ew')
        self._css_browse = Button(oframe2, text="Browse",
                                  command=self._browse_css,
                                  **BUTTON_CONFIG) 
        self._css_browse.grid(row=i, col=3, sticky='ew', padx=2)

    def _init_bindings(self):
        self._top.bind('<Delete>', self._delete_module)
        self._top.bind('<Alt-o>', self._options_toggle)
        self._top.bind('<Alt-g>', self._go)
        self._top.bind('<Alt-s>', self._go)
        self._top.bind('<Control-g>', self._go)

        self._top.bind('<Control-o>', self._open)
        self._top.bind('<Control-s>', self._save)
        self._top.bind('<Control-a>', self._saveas)

    def _options_toggle(self, *e):
        if self._options_visible:
            self._option_frame.forget()
            self._option_button['image'] = self._rightImage
            self._options_visible = 0
        else:
            self._option_frame.pack(side="right", fill='both',
                                    expand=0, padx=4, pady=3)
            self._option_button['image'] = self._leftImage
            self._options_visible = 1

    def add_module(self, name, beep=1):
        if DEBUG: print 'importing', name
        try: [module] = _find_modules([name], 0)
        except:
            if beep: self._top.bell()
            return 0
        if module in self._modules:
            if beep: self._top.bell()
            return 0
        self._modules.append(module)
        self._module_list.insert('end', module.__name__)
        return 1

    def _delete_module(self, *e):
        selection = self._module_list.curselection()
        if len(selection) != 1: return
        del self._modules[int(selection[0])]
        self._module_list.delete(selection[0])

    def _entry_module(self, *e):
        self.add_module(self._module_entry.get())
        self._module_entry.delete(0, 'end')

    def _browse_module(self, *e):
        ftypes = [('Python module', '.py'),
                  ('All files', '*')]
        filename = askopenfilename(filetypes=ftypes,
                                   defaultextension='.py')
        if not filename: return
        self.add_module(filename)
        
    def _browse_css(self, *e):
        self._css_var.set('-other-')
        ftypes = [('CSS Stylesheet', '.css'),
                  ('All files', '*')]
        filename = askopenfilename(filetypes=ftypes,
                                   defaultextension='.css')
        if not filename: return
        self._css_entry.delete(0, 'end')
        self._css_entry.insert(0, filename)

    def _browse_out(self, *e):
        ftypes = [('All files', '*')]
        filename = asksaveasfilename(filetypes=ftypes)
        if not filename: return
        self._css_entry.delete(0, 'end')
        self._css_entry.insert(0, filename)

    def destroy(self, *e):
        if self._top is None: return
        self._top.destroy()
        self._top = None

    def mainloop(self, *args, **kwargs):
        self._top.mainloop(*args, **kwargs)

    def _getopts(self):
        options = {}
        options['prj_name'] = self._name_entry.get() or None
        options['prj_url'] = self._url_entry.get() or None
        options['outdir'] = self._out_entry.get() or 'html'
        if self._css_var.get() == '-other-':
            options['css'] = self._css_entry.get() or 'default'
        else:
            options['css'] = self._css_var.get() or 'default'
        return options
    
    def _go(self, *e):
        if len(self._modules) == 0:
            self._top.bell()
            return

        if self._progress[0] != None:
            self._cancel[0] = 1
            return
        
        # Start documenting
        self._progress[0] = 0.0
        self._cancel[0] = 0
        args = (self._modules, self._getopts(),
                self._progress, self._cancel)
        start_new_thread(document, args)

        # Start the progress bar.
        self._go_button['text'] = 'Stop'
        self._afterid += 1
        dt = 300 # How often to update, in milliseconds
        self._update(dt, self._afterid)

    def _update(self, dt, id):
        if self._top is None: return
        if self._progress[0] is None: return
        if id != self._afterid: return

        # Update the progress bar.
        if self._progress[0] == 'done': p = self._W + DX
        elif self._progress[0] == 'cancel': p = 0
        else: p = DX + self._W * self._progress[0]
        self._canvas.coords(self._r1, DX+1, DY+1, p, self._H+1)
        self._canvas.coords(self._r2, DX, DY, p-1, self._H)
        self._canvas.coords(self._r3, DX+1, DY+1, p, self._H+1)

        # Are we done?
        if self._progress[0] in ('done', 'cancel'):
            self._go_button['text'] = 'Start'
            self._progress[0] = None
            return

        self._top.after(dt, self._update, dt, id)

    def _open(self, *e):
        ftypes = [('Project file', '.prj'),
                  ('All files', '*')]
        filename = askopenfilename(filetypes=ftypes,
                                   defaultextension='.css')
        if not filename: return
        self.open(filename)

    def open(self, prjfile):
        self._filename = prjfile
        if 1:#try:
            opts = load(open(prjfile, 'r'))
            opts['modules'].sort(lambda e1, e2: cmp(e1[1], e2[1]))
            self._name_entry.delete(0, 'end')
            if opts.get('prj_name'):
                self._name_entry.insert(0, opts['prj_name'])
            self._url_entry.delete(0, 'end')
            if opts.get('prj_url'):
                self._url_entry.insert(0, opts['prj_url'])
            self._out_entry.delete(0, 'end')
            self._out_entry.insert(0, opts.get('outdir', 'html'))
            self._css_entry.delete(0, 'end')
            if opts.get('css', 'default') in STYLESHEETS.keys():
                self._css_var.set(opts.get('css', 'default'))
            else:
                self._css_var.set('-other-')
                self._css_entry.insert(0, opts.get('css', 'default'))
            for (file, name) in opts.get('modules', []):
                if not self.add_module(file, 0):
                    self.add_module(name, 0)
        #except:
        #    self._top.bell()
        
    def _save(self, *e):
        if self._filename is None: return self._saveas()
        try:
            opts = self._getopts()
            opts['modules'] = [(hasattr(m, '__file__') and m.__file__,
                                m.__name__)
                               for m in self._modules]
            opts['modules'].sort(lambda e1, e2: cmp(e1[1], e2[1]))
            dump(opts, open(self._filename, 'w'))
        except Exception, e:
            if DEBUG: print e
            self._top.bell()
             
    def _saveas(self, *e): 
        ftypes = [('Project file', '.prj'), ('All files', '*')]
        filename = asksaveasfilename(filetypes=ftypes,
                                     defaultextension='.prj')
        if not filename: return
        self._filename = filename
        self._save()

def gui():
    gui = EpydocGUI()
    for arg in sys.argv[1:]:
        if arg[-4:] == '.prj':
            gui.open(arg)
        else:
            try: gui.add_module(arg)
            except: pass
    gui.mainloop()

if __name__ == '__main__': gui()
