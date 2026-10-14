import ctypes
import ctypes.wintypes
import random
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

APP = 'XClicker Windows'
U = ctypes.windll.user32
BUTTONS = {'Left': (0x0002, 0x0004), 'Right': (0x0008, 0x0010), 'Middle': (0x0020, 0x0040)}
F6, F8 = 0x75, 0x77

class App:
    def __init__(self, root):
        self.root=root; root.title(APP); root.geometry('650x590'); root.minsize(600,550); root.configure(bg='#17151f')
        self.running=False; self.stop_event=threading.Event(); self.closing=False; self.last={F6:False,F8:False}; self.n=0
        self.interval=tk.StringVar(value='100'); self.variance=tk.StringVar(value='0'); self.button=tk.StringVar(value='Left')
        self.kind=tk.StringVar(value='Single'); self.repeat=tk.StringVar(value='0'); self.position=tk.StringVar(value='Cursor')
        self.x=tk.StringVar(value='0'); self.y=tk.StringVar(value='0'); self.top=tk.BooleanVar(value=False)
        self.status=tk.StringVar(value='Stopped'); self.count=tk.StringVar(value='0')
        self.ui(); root.after(30,self.hotkeys); root.protocol('WM_DELETE_WINDOW',self.close)
    def ui(self):
        s=ttk.Style(); s.theme_use('clam'); s.configure('TCombobox',fieldbackground='#282432',background='#342c43',foreground='#f6f0ff',arrowcolor='#eee6ff'); s.configure('TEntry',fieldbackground='#282432',foreground='#f6f0ff')
        h=tk.Frame(self.root,bg='#241b35',padx=22,pady=16); h.pack(fill='x')
        tk.Label(h,text='XClicker',bg='#241b35',fg='#f7f1ff',font=('Segoe UI',23,'bold')).pack(anchor='w')
        tk.Label(h,text='Windows edition • lightweight mouse automation',bg='#241b35',fg='#bba8df').pack(anchor='w')
        b=tk.Frame(self.root,bg='#17151f',padx=22,pady=12); b.pack(fill='both',expand=True)
        def heading(t): tk.Label(b,text=t.upper(),bg='#17151f',fg='#bda7ef',font=('Segoe UI',9,'bold')).pack(anchor='w',pady=(10,6))
        g=tk.Frame(b,bg='#17151f'); g.pack(fill='x'); g.columnconfigure(1,weight=1); g.columnconfigure(3,weight=1)
        def lab(t,r,c): tk.Label(g,text=t,bg='#17151f',fg='#eee7f8').grid(row=r,column=c,sticky='w',padx=(0,8),pady=6)
        lab('Interval (ms)',0,0); ttk.Entry(g,textvariable=self.interval).grid(row=0,column=1,sticky='ew',padx=(0,12),pady=5)
        lab('Mouse button',0,2); ttk.Combobox(g,textvariable=self.button,values=list(BUTTONS),state='readonly').grid(row=0,column=3,sticky='ew',pady=5)
        lab('Click type',1,0); ttk.Combobox(g,textvariable=self.kind,values=['Single','Double'],state='readonly').grid(row=1,column=1,sticky='ew',padx=(0,12),pady=5)
        lab('Repeat count',1,2); ttk.Entry(g,textvariable=self.repeat).grid(row=1,column=3,sticky='ew',pady=5)
        lab('Random variance (± ms)',2,0); ttk.Entry(g,textvariable=self.variance).grid(row=2,column=1,sticky='ew',padx=(0,12),pady=5)
        tk.Label(g,text='0 = unlimited clicks',bg='#17151f',fg='#9f96b2').grid(row=2,column=2,columnspan=2,sticky='w')
        heading('Click position'); p=tk.Frame(b,bg='#211d2a',padx=10,pady=8); p.pack(fill='x')
        for t,v in [('Follow cursor','Cursor'),('Fixed coordinates','Fixed')]: tk.Radiobutton(p,text=t,variable=self.position,value=v,bg='#211d2a',fg='#f0eafa',selectcolor='#49365f',activebackground='#211d2a').pack(side='left',padx=(0,12))
        c=tk.Frame(p,bg='#211d2a'); c.pack(side='right')
        tk.Label(c,text='X',bg='#211d2a',fg='#c7badb').pack(side='left'); ttk.Entry(c,textvariable=self.x,width=7).pack(side='left',padx=4)
        tk.Label(c,text='Y',bg='#211d2a',fg='#c7badb').pack(side='left'); ttk.Entry(c,textvariable=self.y,width=7).pack(side='left',padx=4)
        tk.Button(c,text='Capture',command=self.capture,bg='#443654',fg='white',relief='flat').pack(side='left',padx=4)
        heading('Controls'); row=tk.Frame(b,bg='#17151f'); row.pack(fill='x')
        self.startbtn=tk.Button(row,text='▶ Start (F6)',command=self.toggle,bg='#8758e8',fg='white',font=('Segoe UI',11,'bold'),relief='flat',padx=18,pady=10); self.startbtn.pack(side='left',fill='x',expand=True,padx=(0,8))
        tk.Button(row,text='■ Stop (F8)',command=self.stop,bg='#393243',fg='white',relief='flat',padx=18,pady=10).pack(side='left')
        tk.Button(row,text='Reset counter',command=self.reset,bg='#393243',fg='white',relief='flat',padx=10,pady=10).pack(side='left',padx=(8,0))
        st=tk.Frame(b,bg='#211d2a',padx=12,pady=10); st.pack(fill='x',pady=(12,0))
        self.dot=tk.Label(st,text='●',bg='#211d2a',fg='#e06b86'); self.dot.pack(side='left')
        tk.Label(st,textvariable=self.status,bg='#211d2a',fg='#f6f0ff',font=('Segoe UI',10,'bold')).pack(side='left',padx=(6,16))
        tk.Label(st,text='Clicks:',bg='#211d2a',fg='#bba8df').pack(side='left'); tk.Label(st,textvariable=self.count,bg='#211d2a',fg='white',font=('Segoe UI',11,'bold')).pack(side='left',padx=5)
        ttk.Checkbutton(b,text='Always on top',variable=self.top,command=lambda:self.root.attributes('-topmost',self.top.get())).pack(anchor='w',pady=(12,0))
        tk.Label(b,text='Hotkeys: F6 start/stop • F8 stop • Esc stops when window is focused',bg='#17151f',fg='#9f96b2',font=('Segoe UI',8)).pack(anchor='w',pady=(8,0))
        root.bind('<Escape>',lambda e:self.stop())
    def capture(self):
        p=ctypes.wintypes.POINT()
        if U.GetCursorPos(ctypes.byref(p)): self.x.set(str(p.x)); self.y.set(str(p.y)); self.position.set('Fixed')
    def reset(self):
        if not self.running: self.n=0; self.count.set('0')
    def toggle(self): self.stop() if self.running else self.start()
    def start(self):
        try:
            ms=int(self.interval.get()); var=int(self.variance.get()); repeat=int(self.repeat.get()); x=int(self.x.get()); y=int(self.y.get())
            if not 10<=ms<=3600000 or not 0<=var<=ms or repeat<0: raise ValueError
        except ValueError: messagebox.showerror(APP,'Use whole numbers. Interval: 10–3,600,000 ms; variance: 0–interval; repeat: 0 or greater.'); return
        self.cfg=(ms/1000,var/1000,repeat,(x,y) if self.position.get()=='Fixed' else None,self.button.get(),self.kind.get())
        self.running=True; self.stop_event.clear(); self.n=0; self.count.set('0'); self.status.set('Running'); self.dot.configure(fg='#7be0a1'); self.startbtn.configure(text='Ⅱ Stop (F6)')
        threading.Thread(target=self.loop,daemon=True).start()
    def stop(self):
        self.stop_event.set(); self.running=False
        if hasattr(self,'status'): self.status.set('Stopped'); self.dot.configure(fg='#e06b86'); self.startbtn.configure(text='▶ Start (F6)')
    def loop(self):
        ms,var,repeat,xy,button,kind=self.cfg; n=0; deadline=time.perf_counter()
        try:
            while not self.stop_event.is_set() and (repeat==0 or n<repeat):
                if xy is not None: U.SetCursorPos(*xy)
                down,up=BUTTONS[button]; U.mouse_event(down,0,0,0,0); U.mouse_event(up,0,0,0,0)
                if kind=='Double':
                    if self.stop_event.wait(.035): break
                    U.mouse_event(down,0,0,0,0); U.mouse_event(up,0,0,0,0)
                n+=1; self.root.after(0,self.update,n)
                deadline+=max(.001,ms+random.uniform(-var,var) if var else ms)
                if self.stop_event.wait(max(0,deadline-time.perf_counter())): break
        finally: self.root.after(0,self.finished)
    def update(self,n): self.n=n; self.count.set(str(n))
    def finished(self):
        self.running=False; self.status.set('Stopped'); self.dot.configure(fg='#e06b86'); self.startbtn.configure(text='▶ Start (F6)')
    def hotkeys(self):
        if self.closing:return
        for key,fn in ((F6,self.toggle),(F8,self.stop)):
            down=bool(U.GetAsyncKeyState(key)&0x8000)
            if down and not self.last.get(key,False): fn()
            self.last[key]=down
        self.root.after(30,self.hotkeys)
    def close(self): self.closing=True; self.stop_event.set(); self.root.destroy()

if __name__=='__main__':
    root=tk.Tk(); App(root); root.mainloop()
