"""
Dark Theme for Benedito Digital GUI
Professional video editor inspired dark theme
"""

import tkinter as tk
from tkinter import ttk

class DarkTheme:
    """Dark theme configuration for professional video editor look"""

    # Color palette - Cinematic purple dark
    COLORS = {
        # Background colors
        'bg_primary': '#0f0b17',      # Main background
        'bg_secondary': '#171124',    # Secondary panels
        'bg_tertiary': '#231733',     # Tertiary elements
        'bg_hover': '#2c1f3f',        # Hover state
        'bg_active': '#35244b',       # Active/selected

        # Text colors
        'text_primary': '#f7f2ff',     # Main text
        'text_secondary': '#c8bfe2',  # Secondary text
        'text_muted': '#8f83b4',      # Muted text
        'text_inverse': '#0b0712',    # Text on colored backgrounds

        # Accent colors (purple focus)
        'accent_primary': '#a855f7',   # Primary accent (purple)
        'accent_secondary': '#c084fc', # Secondary accent (light purple)
        'accent_success': '#22c55e',   # Success (green)
        'accent_warning': '#fbbf24',   # Warning (yellow)
        'accent_error': '#f43f5e',     # Error (red)

        # Border colors
        'border_light': '#2b1f3a',     # Light borders
        'border_medium': '#3a2a4a',    # Medium borders
        'border_dark': '#120c1d',      # Dark borders

        # Special colors
        'timeline_bg': '#0b0910',     # Timeline background
        'timeline_track': '#171323',   # Track background
        'timeline_clip': '#a855f7',    # Clip color
        'timeline_playhead': '#c084fc', # Playhead color

        # Video player colors
        'player_bg': '#06050b',        # Player background
        'player_controls': '#120c1d',  # Controls background
        'player_progress': '#a855f7',  # Progress bar

        # Button colors
        'button_primary': '#a855f7',   # Primary button
        'button_secondary': '#35244b',  # Secondary button
        'button_danger': '#f43f5e',    # Danger button
    }

    FONTS = {
        'title': ('Bahnschrift SemiBold', 12),
        'subtitle': ('Bahnschrift', 10),
        'body': ('Trebuchet MS', 10),
        'small': ('Trebuchet MS', 9),
        'mono': ('Cascadia Mono', 10),
    }

    @classmethod
    def configure_tkinter(cls, root):
        """Configure tkinter root with dark theme"""
        root.configure(bg=cls.COLORS['bg_primary'])

        # Configure styles
        style = ttk.Style()
        style.theme_use('clam')  # Use clam as base theme

        # Configure ttk styles
        cls.configure_ttk_styles(style)

    @classmethod
    def apply_accessibility(cls, root, preferences):
        """Apply focus visibility and optional high-contrast colors."""
        style = ttk.Style(root)
        focus = "#ffffff" if preferences.high_contrast else cls.COLORS['accent_secondary']
        background = "#000000" if preferences.high_contrast else cls.COLORS['bg_primary']
        foreground = "#ffffff" if preferences.high_contrast else cls.COLORS['text_primary']
        root.configure(bg=background)
        root.option_add("*highlightColor", focus)
        focus_thickness = 2 if preferences.large_focus else 1
        for widget_class in (
            "Button",
            "Checkbutton",
            "Radiobutton",
            "Entry",
            "Listbox",
            "Scale",
            "Spinbox",
            "Text",
        ):
            root.option_add(f"*{widget_class}.takeFocus", True)
            root.option_add(
                f"*{widget_class}.highlightThickness", focus_thickness
            )
        style.configure("TButton", focuscolor=focus, focusthickness=3 if preferences.large_focus else 1)
        style.configure("TEntry", fieldbackground=background, foreground=foreground, insertcolor=focus)
        style.configure("TCombobox", fieldbackground=background, foreground=foreground)

    @classmethod
    def configure_ttk_styles(cls, style):
        """Configure all ttk styles with dark theme"""

        # Frame styles
        style.configure('Dark.TFrame',
                      background=cls.COLORS['bg_primary'])
        style.configure('DarkSecondary.TFrame',
                      background=cls.COLORS['bg_secondary'])
        style.configure('DarkTertiary.TFrame',
                      background=cls.COLORS['bg_tertiary'])

        # Label styles
        style.configure('Dark.TLabel',
                      background=cls.COLORS['bg_primary'],
                      foreground=cls.COLORS['text_primary'],
                      font=cls.FONTS['body'])
        style.configure('DarkSecondary.TLabel',
                      background=cls.COLORS['bg_secondary'],
                      foreground=cls.COLORS['text_secondary'],
                      font=cls.FONTS['body'])
        style.configure('DarkMuted.TLabel',
                      background=cls.COLORS['bg_primary'],
                      foreground=cls.COLORS['text_muted'],
                      font=cls.FONTS['small'])
        style.configure('DarkAccent.TLabel',
                      background=cls.COLORS['bg_primary'],
                      foreground=cls.COLORS['accent_primary'],
                      font=cls.FONTS['subtitle'])

        # Button styles
        style.configure('Dark.TButton',
                      background=cls.COLORS['bg_tertiary'],
                      foreground=cls.COLORS['text_primary'],
                      font=cls.FONTS['body'],
                      borderwidth=1,
                      focuscolor='none')
        style.map('Dark.TButton',
                 background=[('active', cls.COLORS['bg_hover']),
                           ('pressed', cls.COLORS['bg_active'])])

        style.configure('DarkPrimary.TButton',
                      background=cls.COLORS['accent_primary'],
                      foreground=cls.COLORS['text_inverse'],
                      font=cls.FONTS['subtitle'],
                      borderwidth=0,
                      focuscolor='none')
        style.map('DarkPrimary.TButton',
                 background=[('active', cls.COLORS['accent_secondary']),
                           ('pressed', cls.COLORS['accent_secondary'])])

        style.configure('DarkSecondary.TButton',
                      background=cls.COLORS['bg_secondary'],
                      foreground=cls.COLORS['text_primary'],
                      font=cls.FONTS['body'],
                      borderwidth=1,
                      focuscolor='none')
        style.map('DarkSecondary.TButton',
                 background=[('active', cls.COLORS['bg_hover']),
                           ('pressed', cls.COLORS['bg_active'])])

        # Entry styles
        style.configure('Dark.TEntry',
                      background=cls.COLORS['bg_tertiary'],
                      foreground=cls.COLORS['text_primary'],
                      font=cls.FONTS['body'],
                      borderwidth=1,
                      insertcolor=cls.COLORS['accent_primary'])
        style.map('Dark.TEntry',
                 focuscolor=[('focus', cls.COLORS['accent_primary'])])

        # Combobox styles
        style.configure('Dark.TCombobox',
                      background=cls.COLORS['bg_tertiary'],
                      foreground=cls.COLORS['text_primary'],
                      font=cls.FONTS['body'],
                      borderwidth=1,
                      arrowcolor=cls.COLORS['text_secondary'])
        style.map('Dark.TCombobox',
                 background=[('readonly', cls.COLORS['bg_tertiary'])],
                 foreground=[('readonly', cls.COLORS['text_primary'])])

        # Notebook (tabs) styles
        style.configure('Dark.TNotebook',
                      background=cls.COLORS['bg_primary'],
                      borderwidth=0)
        style.configure('Dark.TNotebook.Tab',
                      background=cls.COLORS['bg_secondary'],
                      foreground=cls.COLORS['text_secondary'],
                      font=cls.FONTS['subtitle'],
                      padding=[20, 10])
        style.map('Dark.TNotebook.Tab',
                 background=[('selected', cls.COLORS['bg_tertiary']),
                           ('active', cls.COLORS['bg_hover'])],
                 foreground=[('selected', cls.COLORS['text_primary'])])

        # Progressbar styles
        style.configure('Dark.Horizontal.TProgressbar',
                      background=cls.COLORS['accent_primary'],
                      troughcolor=cls.COLORS['bg_tertiary'],
                      borderwidth=0,
                      lightcolor=cls.COLORS['accent_primary'],
                      darkcolor=cls.COLORS['accent_primary'])

        # Scale styles
        style.configure('Dark.Horizontal.TScale',
                      background=cls.COLORS['bg_primary'],
                      troughcolor=cls.COLORS['bg_tertiary'],
                      slidercolor=cls.COLORS['accent_primary'],
                      borderwidth=0)

        # Scrollbar styles
        style.configure('Dark.Vertical.TScrollbar',
                      background=cls.COLORS['bg_tertiary'],
                      troughcolor=cls.COLORS['bg_secondary'],
                      borderwidth=0,
                      arrowcolor=cls.COLORS['text_secondary'])
        style.map('Dark.Vertical.TScrollbar',
                 background=[('active', cls.COLORS['bg_hover'])])

        # Separator styles
        style.configure('Dark.TSeparator',
                      background=cls.COLORS['border_light'])

    @classmethod
    def create_custom_button(cls, parent, text, command=None, style='Dark.TButton',
                           width=None, height=None):
        """Create a custom styled button"""
        btn = ttk.Button(parent, text=text, command=command, style=style)
        if width:
            btn.configure(width=width)
        if height:
            btn.configure(height=height)
        return btn

    @classmethod
    def create_custom_label(cls, parent, text, style='Dark.TLabel',
                          font=None):
        """Create a custom styled label"""
        label = ttk.Label(parent, text=text, style=style)
        if font:
            label.configure(font=font)
        return label

    @classmethod
    def create_custom_frame(cls, parent, style='Dark.TFrame'):
        """Create a custom styled frame"""
        return ttk.Frame(parent, style=style)

    @classmethod
    def create_gradient_frame(cls, parent, color1, color2, height=30):
        """Create a frame with gradient effect (simulated)"""
        frame = tk.Frame(parent, bg=color1, height=height)
        return frame
