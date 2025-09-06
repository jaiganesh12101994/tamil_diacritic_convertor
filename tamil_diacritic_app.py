# tamil_diacritic_app.py
# Modern Tamil Diacritic Converter - single-file app
# - Uses ttkbootstrap if installed (recommended) otherwise falls back to ttk
# - Tamil script -> diacritic Roman, Roman -> diacritic
# - Custom mappings persisted to mappings.json
# - Robust main() and top-level error logging to app_error.log

import sys
import json
import os
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# Try to use ttkbootstrap for a modern theme; fall back to ttk
USE_TTKBOOTSTRAP = False
try:
    import ttkbootstrap as tb
    from ttkbootstrap.constants import *
    USE_TTKBOOTSTRAP = True
except Exception:
    USE_TTKBOOTSTRAP = False

# -------------------- Transliteration data --------------------
# Tamil codepoints for vowels/consonants are used as literals for clarity
TAMIL_INDEPENDENT_VOWELS = {
    'அ': 'a', 'ஆ': 'ā', 'இ': 'i', 'ஈ': 'ī',
    'உ': 'u', 'ஊ': 'ū', 'எ': 'e', 'ஏ': 'ē',
    'ஐ': 'ai','ஒ': 'o','ஓ': 'ō','ஔ': 'au',
}
TAMIL_VOWEL_SIGNS = {
    'ா':'ā','ி':'i','ீ':'ī','ு':'u','ூ':'ū',
    'ெ':'e','ே':'ē','ை':'ai','ொ':'o','ோ':'ō','ௌ':'au',
}
TAMIL_VIRAMA = '்'
TAMIL_ANUSVARA = 'ஂ'
TAMIL_AAYTHAM = 'ஃ'
PUNCT_MAP = {'।':'.','॥':'.','\u200C':'','\u200D':''}

# Tamil consonants core mapping (including 'ன' -> 'ṉ')
TAMIL_CONSONANTS_CORE = {
    'க':'k','ங':'ṅ','ச':'c','ஞ':'ñ','ட':'ṭ',
    'ண':'ṇ','த':'t','ந':'n','ன':'ṉ','ப':'p',
    'ம':'m','ய':'y','ர':'r','ற':'ṟ','ல':'l',
    'ள':'ḷ','ழ':'ḻ','வ':'v'
}

# Roman->diacritic mapping (basic). You can expand as needed.
ROMAN_MAPPINGS = [
    ("aa","ā"),("ii","ī"),("uu","ū"),("ee","ē"),("oo","ō"),
    ("zh","ḻ"),("ng","ṅ"),("n.","ṇ"),("t.","ṭ"),("l.","ḷ"),
    ("r.","ṛ"),("m.","ṃ"),("sh","ś"),("ch","ch")
]

# -------------------- Utility functions --------------------
def replace_preserve_case(s: str, src: str, tgt: str) -> str:
    # replace respecting capitalization for first-letter words & all-caps
    out = s.replace(src, tgt)
    if src and src[0].isalpha():
        out = out.replace(src.capitalize(), tgt.capitalize())
        out = out.replace(src.upper(), ''.join(ch.upper() if ch.isalpha() else ch for ch in tgt))
    return out

def apply_roman_mappings(text: str):
    out = text
    for src, tgt in sorted(ROMAN_MAPPINGS, key=lambda x: -len(x[0])):
        out = replace_preserve_case(out, src, tgt)
    return out

def build_consonant_map(use_sanskrit: bool):
    cmap = dict(TAMIL_CONSONANTS_CORE)
    # Grantha / Sanskrit mode: map ஜ ஶ ஷ ஸ to j/ś/ṣ/s or s/sh etc.
    if use_sanskrit:
        cmap['ஜ'] = 'j'; cmap['ஷ'] = 'ṣ'; cmap['ஸ'] = 's'; cmap['ஹ'] = 'h'; cmap['ஶ'] = 'ś'
    else:
        cmap['ஜ'] = 'j'; cmap['ஷ'] = 'sh'; cmap['ஸ'] = 's'; cmap['ஹ'] = 'h'; cmap['ஶ'] = 's'
    return cmap

def is_tamil_char(ch: str) -> bool:
    return '\u0B80' <= ch <= '\u0BFF'

def tamil_to_diacritic_roman(text: str, use_sanskrit: bool=True) -> str:
    TAMIL_CONSONANTS = build_consonant_map(use_sanskrit)
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in PUNCT_MAP:
            out.append(PUNCT_MAP[ch]); i += 1; continue
        if ch == TAMIL_ANUSVARA:
            out.append('ṃ'); i += 1; continue
        if ch == TAMIL_AAYTHAM:
            out.append('ḥ'); i += 1; continue
        if ch in TAMIL_INDEPENDENT_VOWELS:
            out.append(TAMIL_INDEPENDENT_VOWELS[ch]); i += 1; continue
        if ch in TAMIL_CONSONANTS:
            base = TAMIL_CONSONANTS[ch]
            nxt = text[i+1] if (i+1) < n else ''
            if nxt == TAMIL_VIRAMA:
                out.append(base); i += 2; continue
            if nxt in TAMIL_VOWEL_SIGNS:
                out.append(base + TAMIL_VOWEL_SIGNS[nxt]); i += 2; continue
            out.append(base + 'a'); i += 1; continue
        # whitespace or other scripts: keep as-is
        out.append(ch); i += 1
    return ''.join(out)

def apply_custom_mappings(text: str, rules):
    out = text
    for s, t in sorted(rules, key=lambda x: -len(x[0])):
        out = out.replace(s, t)
    return out

# -------------------- App (GUI) --------------------
class TamilDiacriticApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Agathiyam Tamil Diacritic Converter - by Dr Jaiganesh")
        self.root.geometry("1000x700")
        self.custom_rules = []  # list of (src, tgt)
        self.mappings_path = os.path.join(os.path.dirname(__file__), "mappings.json")
        self.use_sanskrit = tk.BooleanVar(value=True)
        self.input_mode = tk.StringVar(value="Tamil")
        self.debug_mode = tk.BooleanVar(value=False)

        self._load_mappings()
        self._build_ui()

    def _load_mappings(self):
        try:
            if os.path.exists(self.mappings_path):
                with open(self.mappings_path, "r", encoding="utf-8") as f:
                    self.custom_rules = json.load(f)
        except Exception:
            self.custom_rules = []

    def _save_mappings(self):
        try:
            with open(self.mappings_path, "w", encoding="utf-8") as f:
                json.dump(self.custom_rules, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    def _build_ui(self):
        # choose theme window
        if USE_TTKBOOTSTRAP:
            style = tb.Style()
        else:
            style = ttk.Style(self.root)
            try:
                style.theme_use("clam")
            except Exception:
                pass

        # Top toolbar
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill='x', padx=10, pady=8)

        ttk.Label(toolbar, text="Input type:").pack(side='left')
        ttk.Radiobutton(toolbar, text="Tamil script", variable=self.input_mode, value="Tamil").pack(side='left', padx=6)
        ttk.Radiobutton(toolbar, text="Roman (translit)", variable=self.input_mode, value="Roman").pack(side='left', padx=6)
        ttk.Checkbutton(toolbar, text="Sanskrit (Grantha) mode", variable=self.use_sanskrit).pack(side='left', padx=12)
        ttk.Checkbutton(toolbar, text="Debug (log)", variable=self.debug_mode).pack(side='left', padx=12)

        ttk.Button(toolbar, text="Load", command=self.load_file).pack(side='right', padx=6)
        ttk.Button(toolbar, text="Save Output", command=self.save_output).pack(side='right', padx=6)

        # Main panes
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=8)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0,6))
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side='left', fill='both', expand=True, padx=(6,0))

        # Input
        ttk.Label(left_frame, text="Input").pack(anchor='w')
        self.input_box = tk.Text(left_frame, wrap='word', height=25)
        self.input_box.pack(fill='both', expand=True, pady=6)

        left_controls = ttk.Frame(left_frame)
        left_controls.pack(fill='x')
        ttk.Button(left_controls, text="Clear", command=lambda: self.input_box.delete('1.0','end')).pack(side='left')
        ttk.Button(left_controls, text="Quick Example", command=self.insert_example).pack(side='left', padx=6)
        ttk.Button(left_controls, text="Convert (Ctrl+Enter)", command=self.convert_now).pack(side='right')

        # Output
        ttk.Label(right_frame, text="Output (diacritic Roman)").pack(anchor='w')
        self.output_box = tk.Text(right_frame, wrap='word', height=25, bg='#fbfbfe')
        self.output_box.pack(fill='both', expand=True, pady=6)

        right_controls = ttk.Frame(right_frame)
        right_controls.pack(fill='x')
        ttk.Button(right_controls, text="Copy", command=self.copy_output).pack(side='left')
        ttk.Button(right_controls, text="Save", command=self.save_output).pack(side='left', padx=6)
        ttk.Button(right_controls, text="Custom Mappings", command=self.open_mappings_editor).pack(side='right')

        # Status bar
        self.status = ttk.Label(self.root, text="Ready", anchor='w')
        self.status.pack(fill='x', side='bottom')

        # Bindings
        self.root.bind('<Control-Return>', lambda e: self.convert_now())

    # ---------------- actions ----------------
    def insert_example(self):
        sample = "தமிழ்: நான் மண்\nRoman: kaakkaa n."
        self.input_box.delete('1.0','end'); self.input_box.insert('1.0', sample)

    def convert_now(self):
        src = self.input_box.get('1.0','end').strip()
        if not src:
            self.status.config(text="No input")
            return
        try:
            if self.input_mode.get() == "Roman":
                converted = apply_roman_mappings(src)
            else:
                converted = tamil_to_diacritic_roman(src, use_sanskrit=self.use_sanskrit.get())
            if self.custom_rules:
                converted = apply_custom_mappings(converted, self.custom_rules)
            self.output_box.delete('1.0','end')
            self.output_box.insert('1.0', converted)
            self.status.config(text="Conversion finished")
            if self.debug_mode.get():
                self._append_log("Converted text length: %d" % len(converted))
        except Exception as e:
            self._append_log("Conversion error: " + str(e))
            messagebox.showerror("Error", str(e))

    def copy_output(self):
        out = self.output_box.get('1.0','end').strip()
        if out:
            self.root.clipboard_clear()
            self.root.clipboard_append(out)
            self.status.config(text="Copied to clipboard")

    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text files","*.txt;*.text"),("All","*.*")])
        if not path: return
        try:
            with open(path,'r',encoding='utf-8') as f:
                data = f.read()
            self.input_box.delete('1.0','end'); self.input_box.insert('1.0', data)
            self.status.config(text=f"Loaded {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_output(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text","*.txt"),("All","*.*")])
        if not path: return
        try:
            with open(path,'w',encoding='utf-8') as f:
                f.write(self.output_box.get('1.0','end'))
            self.status.config(text=f"Saved {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---------------- custom mappings editor ----------------
    def open_mappings_editor(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Custom Mappings")
        dlg.geometry("520x360")
        tree = ttk.Treeview(dlg, columns=('src','tgt'), show='headings', height=10)
        tree.heading('src', text='Source')
        tree.heading('tgt', text='Target')
        tree.pack(fill='both', expand=True, padx=8, pady=8)
        for s,t in self.custom_rules:
            tree.insert('', 'end', values=(s,t))
        btns = ttk.Frame(dlg)
        btns.pack(fill='x', padx=8, pady=(0,8))
        def add_map():
            s = simpledialog.askstring("Source","Source text:", parent=dlg)
            if s is None: return
            t = simpledialog.askstring("Target","Target text:", parent=dlg)
            if t is None: return
            self.custom_rules.append((s,t))
            tree.insert('', 'end', values=(s,t))
        def edit_map():
            sel = tree.selection()
            if not sel: return
            iid = sel[0]; s,t = tree.item(iid,'values')
            ns = simpledialog.askstring("Source","Source text:",initialvalue=s,parent=dlg)
            if ns is None: return
            nt = simpledialog.askstring("Target","Target text:",initialvalue=t,parent=dlg)
            if nt is None: return
            idx = tree.index(iid)
            self.custom_rules[idx] = (ns,nt)
            tree.item(iid, values=(ns,nt))
        def del_map():
            sel = tree.selection()
            if not sel: return
            iid = sel[0]; idx = tree.index(iid)
            del self.custom_rules[idx]
            tree.delete(iid)
        ttk.Button(btns, text="Add", command=add_map).pack(side='left')
        ttk.Button(btns, text="Edit", command=edit_map).pack(side='left', padx=6)
        ttk.Button(btns, text="Delete", command=del_map).pack(side='left', padx=6)
        def save_and_close():
            self._save_mappings()
            dlg.destroy()
        ttk.Button(btns, text="Save & Close", command=save_and_close).pack(side='right')

    def _append_log(self, s: str):
        try:
            with open("app_debug.log", "a", encoding="utf-8") as f:
                f.write(s + "\n")
        except Exception:
            pass

# -------------------- top-level run helpers --------------------
def main():
    # top-level run: create window and start app
    try:
        if USE_TTKBOOTSTRAP:
            app_win = tb.Window(themename="litera")  # uses ttkbootstrap
            app = TamilDiacriticApp(app_win)
            app_win.mainloop()
        else:
            root = tk.Tk()
            app = TamilDiacriticApp(root)
            root.mainloop()
    except Exception:
        # Write full traceback to app_error.log so packaging issues can be diagnosed
        with open("app_error.log", "w", encoding="utf-8") as fh:
            fh.write("Unhandled exception in main():\n")
            traceback.print_exc(file=fh)
        # Also show a messagebox if possible
        try:
            messagebox.showerror("Fatal error", "An unhandled error occurred. See app_error.log")
        except Exception:
            pass
        raise

if __name__ == "__main__":
    main()
