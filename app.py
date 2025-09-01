# app.py (Refactored to use GameManager)

from flask import Flask, render_template, jsonify, request
import time
import sys
import logging

# --- Setup Logging ---
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

try:
    from quoridor_logic import QuoridorGame, BOARD_SIZE
    from quoridor_bot import QuoridorBot
except ImportError as e:
    print(f"!! Import Error: {e}")
    sys.exit(1)

# --- Constants ---
HUMAN_PLAYER_ID = 2
BOT_PLAYER_ID = 1
BOT_SEARCH_DEPTH = 3

class GameManager:
    """
    Manages the state and logic of a single Quoridor game.
    This encapsulates the game state, removing the need for global variables.
    """
    def __init__(self):
        self.game = QuoridorGame()
        self.bot = QuoridorBot(player_id=BOT_PLAYER_ID, search_depth=BOT_SEARCH_DEPTH)
        self.turn_count = 1
        self.game_active = False

    def _log_state_short(self):
        """Helper for compact console logging."""
        state = self.game.get_state_dict()
        p1p = state.get("p1_pos", "?")
        p2p = state.get("p2_pos", "?")
        p1w = state.get("p1_walls", "?")
        p2w = state.get("p2_walls", "?")
        cp = state.get("current_player", "?")
        walls_short = [f"W{p[1]}{p[2]}" for w in state.get("placed_walls", []) if len(p := w.split()) == 3]
        walls_str = ",".join(sorted(walls_short)) if walls_short else "[]"
        return f"[G1/T{self.turn_count}] P{cp} S(B:{p1p}({p1w}) H:{p2p}({p2w})|W:{walls_str})"

    def start_new_game(self):
        """Initializes a new game."""
        print("\n[LOG] ### GAME START ###")
        self.game = QuoridorGame()
        self.turn_count = 1
        self.game_active = True
        status_msg = "Game Started!"
        print(f"{self._log_state_short()} - Init State")

        # If the bot is Player 1, it makes the first move.
        if self.game.current_player == BOT_PLAYER_ID:
            print("[LOG] Initial Bot Turn...")
            status_msg = self._run_bot_turn()
        else:
            status_msg = "Game Started! Your turn (P2)."

        return self.get_game_state(status_msg)

    def get_game_state(self, status_message=None):
        """Returns the current state of the game, suitable for JSON responses."""
        state = self.game.get_state_dict()
        state['turn_count'] = self.turn_count
        state['game_active'] = self.game_active
        state['human_player_id'] = HUMAN_PLAYER_ID
        state['valid_moves'] = {'pawn': [], 'wall': []} # Default empty

        # Add a status message if one isn't provided
        if status_message:
            state['status_message'] = status_message
        elif self.game.is_game_over():
            state['status_message'] = f"Game Over! Player {self.game.winner} Wins!"
        elif not self.game_active:
            state['status_message'] = "Click Start to Play"
        elif state['current_player'] == HUMAN_PLAYER_ID:
            state['status_message'] = f"Your turn (P{HUMAN_PLAYER_ID})"
            # If it's the human's turn, calculate and include valid moves
            valid_pawn_pos = self.game.get_valid_pawn_moves(HUMAN_PLAYER_ID)
            valid_pawn_coords = [self.game._pos_to_coord(pos) for pos in valid_pawn_pos]
            valid_walls = self.game.get_valid_wall_placements(HUMAN_PLAYER_ID)
            state['valid_moves'] = {
                'pawn': [coord for coord in valid_pawn_coords if coord], # Filter out None
                'wall': valid_walls
            }
        else:
            state['status_message'] = f"P{BOT_PLAYER_ID}(Bot) is thinking..."

        return state

    def make_human_move(self, move_string):
        """
        Processes a move from the human player and then triggers the bot's turn.
        """
        if not self.game_active or self.game.is_game_over():
            return {"success": False, "reason": "Game is not active.", "game_state": self.get_game_state()}
        if self.game.current_player != HUMAN_PLAYER_ID:
            return {"success": False, "reason": "Not your turn.", "game_state": self.get_game_state()}
        if not move_string:
            return {"success": False, "reason": "No move provided.", "game_state": self.get_game_state()}

        print(f"{self._log_state_short()} - Human Recv: '{move_string}'")

        success, reason_code = self.game.make_move(move_string)

        if not success:
            print(f"  FAIL: P{HUMAN_PLAYER_ID}(H) tried '{move_string}'. Reason: {reason_code}")
            status_message = f"Your Move Failed: '{move_string}' ({reason_code})"
            return {"success": False, "reason": reason_code, "game_state": self.get_game_state(status_message)}

        print(f"  OK: P{HUMAN_PLAYER_ID}(H) played {move_string}")

        # Check for human win
        if self.game.is_game_over():
            self.game_active = False
            status_message = f"Game Over! You (P{self.game.winner}) Win!"
            print(f"[LOG] ### GAME OVER ### Winner: P{self.game.winner} (Human)")
            return {"success": True, "reason": None, "game_state": self.get_game_state(status_message)}

        # Human move was successful, now it's the bot's turn.
        bot_status = self._run_bot_turn()

        # Check for bot win
        if self.game.is_game_over():
            self.game_active = False
            status_message = f"Game Over! Bot (P{self.game.winner}) Wins!"
            print(f"[LOG] ### GAME OVER ### Winner: P{self.game.winner} (Bot)")
        else:
            status_message = bot_status
            self.turn_count += 1 # Increment turn after both players have moved

        return {"success": True, "reason": None, "game_state": self.get_game_state(status_message)}

    def _run_bot_turn(self):
        """
        Finds and executes the bot's move.
        Returns a status message about the outcome.
        """
        if self.game.current_player != BOT_PLAYER_ID:
            error_msg = f"Error: _run_bot_turn called when it is P{self.game.current_player}'s turn."
            print(error_msg)
            return error_msg

        print(f"{self._log_state_short()} - Bot Turn Start")

        best_move = self.bot.find_best_move(self.game)

        if not best_move:
            status_message = f"P{BOT_PLAYER_ID}(Bot) ERR: No valid moves found - Skipping!"
            print(f"!!CRITICAL: Bot P{BOT_PLAYER_ID} found no moves. Skipping turn.")
            self.game.current_player = self.game.get_opponent(BOT_PLAYER_ID) # Manually skip turn
            return status_message

        success, reason_code = self.game.make_move(best_move)
        if success:
            status_message = f"P{BOT_PLAYER_ID}(Bot) played {best_move}"
            print(f"  OK: P{BOT_PLAYER_ID} played {best_move}")
        else:
            # This should ideally not happen if find_best_move is correct.
            status_message = f"P{BOT_PLAYER_ID}(Bot) ERR: Suggested move {best_move} failed ({reason_code}) - Skipping!"
            print(f"!!CRITICAL: Bot suggested invalid move '{best_move}'. Reason: {reason_code}. Skipping turn.")
            self.game.current_player = self.game.get_opponent(BOT_PLAYER_ID) # Manually skip turn

        return status_message

# --- Flask App Setup ---
app = Flask(__name__)
game_manager = GameManager() # Create a single game manager instance

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html', board_size=BOARD_SIZE, human_player_id=HUMAN_PLAYER_ID)

@app.route('/start_game', methods=['POST'])
def start_game():
    game_state = game_manager.start_new_game()
    return jsonify({"success": True, "message": game_state['status_message'], "game_state": game_state})

@app.route('/make_human_move', methods=['POST'])
def make_human_move():
    data = request.get_json()
    move_string = data.get('move')
    result = game_manager.make_human_move(move_string)
    return jsonify(result)

@app.route('/game_state')
def get_game_state_poll():
    """This endpoint is used for polling to get the latest game state."""
    return jsonify(game_manager.get_game_state())

if __name__ == '__main__':
    print("Starting Flask server for Quoridor (Human vs AlgoBot)...")
    app.run(debug=False, host='0.0.0.0', port=25565)