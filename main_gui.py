# main_gui.py (Retry Logic Integrated - Fixed Sleep Delay)

import tkinter as tk
import customtkinter
from tkinter import messagebox
import time
import sys
import requests
import random # Keep import for potential future use

# Import game logic, constants, and Ollama interface functions
try:
    from quoridor_logic import QuoridorGame, BOARD_SIZE
    from ollama_interface import create_quoridor_prompt, get_llm_move, validate_move_format
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Ensure quoridor_logic.py and ollama_interface.py are in the same directory.")
    sys.exit(1)

# --- Hardcoded Configuration ---
OLLAMA_API_URL_MAIN = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL_MAIN = OLLAMA_API_URL_MAIN.replace("/api/generate", "/api/tags")

# --- Theme and Appearance (CustomTkinter) ---
customtkinter.set_appearance_mode("dark")
customtkinter.set_default_color_theme("blue")

# --- GUI Configuration ---
CELL_SIZE = 55
WALL_THICKNESS = 10
PAWN_RADIUS = CELL_SIZE // 3.5
BOARD_PIXELS = BOARD_SIZE * CELL_SIZE
CANVAS_PADDING = CELL_SIZE // 2
CANVAS_WIDTH = BOARD_PIXELS + 2 * CANVAS_PADDING
CANVAS_HEIGHT = BOARD_PIXELS + 2 * CANVAS_PADDING
INFO_HEIGHT = 60

# --- Dark Theme Color Palette ---
COLOR_BACKGROUND = "#2B2B2B"; COLOR_BOARD = "#3C3F41"; COLOR_GRID = "#555555"
COLOR_P1 = "#E0E0E0"; COLOR_P2 = "#606060"; COLOR_WALL = "#A06040" # Muted Brown/Orange
COLOR_GOAL = "#455A45"; COLOR_ACTIVE_PLAYER = "#00A0FF"; COLOR_STATUS_TEXT = "#C0C0C0"

# --- Game Loop Configuration ---
MOVE_DELAY_MS = 300 # Delay AFTER a successful turn or final failure (in milliseconds)
MAX_RETRIES_PER_TURN = 1 # Allow one retry attempt after first failure

# --- Console Logging Helper ---
def format_state_short(game_state):
    """Creates an abbreviated state string for console display."""
    p1p=game_state.get("p1_pos", "?"); p2p=game_state.get("p2_pos", "?")
    p1w=game_state.get("p1_walls", "?"); p2w=game_state.get("p2_walls", "?")
    cp=game_state.get("current_player", "?")
    walls_short=[f"W{p[1]}{p[2]}" for w in game_state.get("placed_walls", []) if len(p := w.split()) == 3]
    walls_str=",".join(sorted(walls_short)) if walls_short else "[]"
    return f"P1:{p1p}({p1w}) P2:{p2p}({p2w}) | Walls:{walls_str} | Turn:{cp}"


class QuoridorGUI(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("Quoridor - LLM Championship (Retry Mode)")
        self.geometry(f"{int(CANVAS_WIDTH + 20)}x{int(CANVAS_HEIGHT + INFO_HEIGHT + 20)}")
        self.configure(fg_color=COLOR_BACKGROUND)
        self.minsize(int(CANVAS_WIDTH*0.8), int((CANVAS_HEIGHT + INFO_HEIGHT)*0.8))

        self.game = QuoridorGame()
        self.turn_count = 1

        # --- Game State Labels ---
        self.info_frame = customtkinter.CTkFrame(self, height=INFO_HEIGHT, corner_radius=0, fg_color="transparent")
        self.info_frame.pack(fill=tk.X, side=tk.TOP, padx=10, pady=(5, 0))
        self.info_frame.columnconfigure(4, weight=1)
        self.player_label_var = tk.StringVar(); self.p1_walls_var = tk.StringVar()
        self.p2_walls_var = tk.StringVar(); self.status_var = tk.StringVar()
        self.turn_label_var = tk.StringVar()
        label_font = ("Arial", 14); status_font = ("Arial", 12, "italic")
        customtkinter.CTkLabel(self.info_frame, textvariable=self.turn_label_var, font=label_font, text_color=COLOR_STATUS_TEXT).grid(row=0, column=0, padx=10, sticky="w")
        customtkinter.CTkLabel(self.info_frame, textvariable=self.player_label_var, font=label_font, text_color=COLOR_STATUS_TEXT).grid(row=0, column=1, padx=10, sticky="w")
        customtkinter.CTkLabel(self.info_frame, textvariable=self.p1_walls_var, font=label_font, text_color=COLOR_STATUS_TEXT).grid(row=0, column=2, padx=10, sticky="w")
        customtkinter.CTkLabel(self.info_frame, textvariable=self.p2_walls_var, font=label_font, text_color=COLOR_STATUS_TEXT).grid(row=0, column=3, padx=10, sticky="w")
        self.status_label_widget = customtkinter.CTkLabel(self.info_frame, textvariable=self.status_var, font=status_font, text_color=COLOR_STATUS_TEXT, wraplength=400, anchor="e")
        self.status_label_widget.grid(row=0, column=4, padx=10, sticky="ew")

        # --- Canvas for Board ---
        self.canvas = tk.Canvas(self, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg=COLOR_BOARD, highlightthickness=0, borderwidth=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.draw_board()
        self.update_status_labels()

        # Start the game loop
        self.after(MOVE_DELAY_MS // 2, self.run_game_turn)

    # --- Drawing Functions (Unchanged) ---
    def _game_pos_to_canvas_coords(self, r, c):
        x = CANVAS_PADDING + c * CELL_SIZE + CELL_SIZE // 2; y = CANVAS_PADDING + r * CELL_SIZE + CELL_SIZE // 2; return x, y
    def _get_wall_canvas_coords(self, orientation, r, c):
        base_x = CANVAS_PADDING + c * CELL_SIZE; base_y = CANVAS_PADDING + r * CELL_SIZE
        center_x = base_x + CELL_SIZE; center_y = base_y + CELL_SIZE
        if orientation == 'H': y = center_y; x1 = base_x + WALL_THICKNESS // 2; x2 = base_x + 2 * CELL_SIZE - WALL_THICKNESS // 2; return x1, y, x2, y
        elif orientation == 'V': x = center_x; y1 = base_y + WALL_THICKNESS // 2; y2 = base_y + 2 * CELL_SIZE - WALL_THICKNESS // 2; return x, y1, x, y2
        return None
    def draw_board(self):
        self.canvas.delete("all")
        for c in range(BOARD_SIZE): # Goal Rows
            for r_goal in [0, BOARD_SIZE - 1]:
                x, y = self._game_pos_to_canvas_coords(r_goal, c)
                self.canvas.create_rectangle(x-CELL_SIZE//2, y-CELL_SIZE//2, x+CELL_SIZE//2, y+CELL_SIZE//2, fill=COLOR_GOAL, outline="")
        for i in range(BOARD_SIZE + 1): # Grid Lines
            x0,y0=CANVAS_PADDING,CANVAS_PADDING; xn,yn=x0+BOARD_SIZE*CELL_SIZE,y0+BOARD_SIZE*CELL_SIZE
            xc,yc=x0+i*CELL_SIZE,y0+i*CELL_SIZE
            self.canvas.create_line(xc, y0, xc, yn, fill=COLOR_GRID, width=1); self.canvas.create_line(x0, yc, xn, yc, fill=COLOR_GRID, width=1)

    def update_display(self):
        """Redraws dynamic elements (pawns, walls)"""
        self.canvas.delete("pawns"); self.canvas.delete("walls")
        for player_id in [2, 1]: # Draw P2 first so P1 highlight is on top
            if player_id in self.game.pawn_positions:
                pos = self.game.pawn_positions.get(player_id)
                if not pos: continue
                r, c = pos; x, y = self._game_pos_to_canvas_coords(r, c)
                color = COLOR_P1 if player_id == 1 else COLOR_P2
                outline_color = COLOR_ACTIVE_PLAYER if player_id == self.game.current_player else COLOR_GRID
                outline_width = 3 if player_id == self.game.current_player else 1.5
                self.canvas.create_oval(x-PAWN_RADIUS, y-PAWN_RADIUS, x+PAWN_RADIUS, y+PAWN_RADIUS, fill=color, outline=outline_color, width=outline_width, tags="pawns")
        for orientation, r, c in self.game.placed_walls:
             coords = self._get_wall_canvas_coords(orientation, r, c)
             if coords: self.canvas.create_line(coords, fill=COLOR_WALL, width=WALL_THICKNESS, tags="walls", capstyle=tk.ROUND)
        self.update_status_labels()
        self.update_idletasks()

    def update_status_labels(self, status_message=""):
        """Updates the text labels in the info bar."""
        self.turn_label_var.set(f"Turn: {self.turn_count}")
        if self.game.is_game_over():
            self.player_label_var.set(f"Game Over!")
            self.status_var.set(f"Player {self.game.winner} wins!")
        else:
            self.player_label_var.set(f"Player Turn: {self.game.current_player}")
            if status_message:
                 max_len = 60; display_msg = status_message if len(status_message) <= max_len else status_message[:max_len-3] + "..."
                 self.status_var.set(display_msg)
            else: self.status_var.set("Waiting...")
        self.p1_walls_var.set(f"P1 Walls: {self.game.walls_left.get(1, 0)}")
        self.p2_walls_var.set(f"P2 Walls: {self.game.walls_left.get(2, 0)}")

    # --- Game Turn Logic ---
    def run_game_turn(self):
        """Executes one turn of the game, using LLM with retry logic."""

        # --- Check Game Over ---
        if self.game.is_game_over():
            self.update_status_labels(f"Player {self.game.winner} has won!")
            messagebox.showinfo("Game Over", f"Player {self.game.winner} has won in {self.turn_count - 1} turns!")
            return # Stop the loop

        # --- Prepare Turn ---
        game_state = self.game.get_state_dict()
        current_player = self.game.current_player
        print(f"\n--- Turn {self.turn_count} ---") # Console Log
        print(f"State: {format_state_short(game_state)}") # Console Log
        self.update_display() # Show current board state before thinking

        # --- Turn Attempt Loop (Retry Logic) ---
        final_move_success = False
        current_turn_failure_reason = None
        llm_move_suggestion = None # Store latest suggestion for logging

        # Loop exactly (1 + MAX_RETRIES_PER_TURN) times maximum
        for attempt in range(1, 1 + MAX_RETRIES_PER_TURN + 1):
            status_msg = f"P{current_player} Thinking (Attempt {attempt})..."
            self.update_status_labels(status_msg) # Update GUI status
            print(status_msg) # Console Log
            self.update_idletasks() # Ensure GUI updates status

            # --- Create Prompt ---
            prompt = None
            valid_pawns_coords_for_prompt = None
            valid_walls_strings_for_prompt = None

            if current_turn_failure_reason: # Is this a retry (attempt > 1)?
                retry_calc_msg = "Calculating valid moves for retry..."
                print(f"INFO: {retry_calc_msg}") # Console Log
                self.update_status_labels(f"P{current_player} Failed ({current_turn_failure_reason}) - Retrying ({retry_calc_msg})")
                self.update_idletasks()

                try:
                    valid_pawn_tuples = self.game.get_valid_pawn_moves(current_player)
                    valid_pawns_coords_for_prompt = sorted([self.game._pos_to_coord(p) for p in valid_pawn_tuples])
                    valid_walls_strings_for_prompt = self.game.get_valid_wall_placements(current_player) # Can be slow
                    found_msg = f"Found {len(valid_pawns_coords_for_prompt)}p / {len(valid_walls_strings_for_prompt)}w valid moves."
                    print(f"INFO: {found_msg}") # Console Log
                    self.update_status_labels(f"P{current_player} Retrying (Attempt {attempt}) - {found_msg}")
                    self.update_idletasks()

                    prompt = create_quoridor_prompt(game_state,
                                                   last_move_fail_reason=current_turn_failure_reason,
                                                   valid_pawn_moves_list=valid_pawns_coords_for_prompt,
                                                   valid_wall_placements_list=valid_walls_strings_for_prompt)
                except Exception as e:
                    error_msg = f"ERROR calculating valid moves for retry: {e}"
                    print(error_msg)
                    self.update_status_labels(f"P{current_player} Error - {error_msg}")
                    current_turn_failure_reason = f"ValidMoveCalcError: {e}"
                    break # Exit attempt loop if calculation fails
            else: # First attempt (attempt == 1)
                prompt = create_quoridor_prompt(game_state)

            # --- Get LLM Move ---
            if prompt is None:
                 current_turn_failure_reason = current_turn_failure_reason or "Prompt Creation Failed"
                 break # Exit attempt loop

            llm_move_suggestion = get_llm_move(prompt) # Console logs happen inside this func

            # --- Validate and Attempt ---
            if not llm_move_suggestion:
                fail_msg = f"API Error/Empty Response"
                print(f"FAIL Attempt {attempt}: P{current_player} - {fail_msg}.") # Console Log
                self.update_status_labels(f"P{current_player} {fail_msg}...")
                current_turn_failure_reason = fail_msg
                if attempt >= (1 + MAX_RETRIES_PER_TURN): break
                # *** CORRECTED SLEEP ***
                time.sleep(MOVE_DELAY_MS / 1000.0) # Use MS value
                continue

            if not validate_move_format(llm_move_suggestion):
                fail_msg = f"Invalid Format '{llm_move_suggestion}'"
                print(f"FAIL Attempt {attempt}: P{current_player} - {fail_msg}.") # Console Log
                self.update_status_labels(f"P{current_player} {fail_msg}...")
                current_turn_failure_reason = "Invalid Move Format"
                if attempt >= (1 + MAX_RETRIES_PER_TURN): break
                # *** CORRECTED SLEEP ***
                time.sleep(MOVE_DELAY_MS / 1000.0) # Use MS value
                continue

            # Attempt the validated format move
            success, reason_code = self.game.make_move(llm_move_suggestion)

            if success:
                status_msg_ok = f"P{current_player} OK: {llm_move_suggestion} (Attempt {attempt})"
                print(status_msg_ok) # Console Log
                self.update_status_labels(status_msg_ok) # Update GUI
                final_move_success = True
                break # Exit the attempt loop on success
            else:
                # Failure occurred
                fail_msg = f"Move Failed: '{llm_move_suggestion}' (Rsn: {reason_code})"
                print(f"FAIL Attempt {attempt}: P{current_player} - {fail_msg}") # Console Log
                self.update_status_labels(f"P{current_player} {fail_msg}...")
                current_turn_failure_reason = reason_code
                if attempt >= (1 + MAX_RETRIES_PER_TURN):
                     break # Exit loop if max retries reached
                # Otherwise, loop continues to the next retry attempt
                # *** CORRECTED SLEEP ***
                time.sleep(MOVE_DELAY_MS / 1000.0) # Use MS value


        # --- After Attempt Loop ---
        if not final_move_success:
            # Log critical failure if all attempts failed
            crit_fail_msg = f"P{current_player} Failed All Attempts (Last: {current_turn_failure_reason}) - Skipping Turn."
            print(f"CRITICAL FAIL: {crit_fail_msg}") # Console Log
            self.update_status_labels(crit_fail_msg) # Update GUI
            # Manually switch player since no valid move was made
            self.game.current_player = self.game.get_opponent(current_player)
            self.update_display() # Show skipped state before scheduling next turn
        else:
            # Update display after successful move
             self.update_display()

        # --- Schedule Next Turn ---
        self.turn_count += 1 # Increment turn number
        # Use self.after for scheduling in Tkinter
        self.after(MOVE_DELAY_MS, self.run_game_turn)


# --- Main Application Entry Point ---
if __name__ == "__main__":
    try:
        # Optional: Initial connection check
        print("Checking Ollama connection...")
        response = requests.get(OLLAMA_TAGS_URL_MAIN, timeout=5)
        if response.status_code == 200: print("Ollama connection successful.")
        else: print(f"Warning: Ollama connection test failed (Status: {response.status_code}). Ensure Ollama is running.")
        # --- End connection check ---

        app = QuoridorGUI() # Create instance of the updated class
        app.mainloop()

    except requests.exceptions.ConnectionError:
         print("\nFATAL ERROR: Could not connect to Ollama server.")
         print(f"Please ensure Ollama is running and accessible at the configured URL ({OLLAMA_API_URL_MAIN}).")
         root = tk.Tk(); root.withdraw(); messagebox.showerror("Connection Error", f"Could not connect to Ollama server ({OLLAMA_API_URL_MAIN}). Please ensure Ollama is running."); root.destroy()
         sys.exit(1)
    except Exception as e:
         print(f"\nAn unexpected error occurred: {e}")
         import traceback; traceback.print_exc()
         root = tk.Tk(); root.withdraw(); messagebox.showerror("Error", f"An unexpected error occurred:\n{e}"); root.destroy()
         sys.exit(1)