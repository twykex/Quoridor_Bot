# app.py (Web GUI V3 - Algo Bot Integration)

from flask import Flask, render_template, jsonify, request
import time
import sys
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
# --- Import ONLY Game Logic and Bot Logic ---
try:
    from quoridor_logic import QuoridorGame, BOARD_SIZE
    from quoridor_bot import QuoridorBot # Import the algorithmic bot
except ImportError as e:
    print(f"!!ImportErr: {e}")
    sys.exit(1)

# --- Flask App Setup ---
app = Flask(__name__)
# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)

# --- Game and Bot Initialization ---
# Global state for the single game instance.
# In a real-world multi-game server, this would be managed in a session object.
game = QuoridorGame()
turn_count = 1
game_active = False
HUMAN_PLAYER_ID = 2
BOT_PLAYER_ID = 1 # Bot is Player 1

# Create the bot instance with desired search depth
# Depth 2 is faster for testing, Depth 3/4 is stronger but slower
BOT_SEARCH_DEPTH = 3
bot = QuoridorBot(player_id=BOT_PLAYER_ID, search_depth=BOT_SEARCH_DEPTH)


# --- Compact Console Logging Helper ---
def format_game_state_for_log(game_state, turn_num):
    """Creates a compact, readable string of the current game state for logging."""
    p1_pos = game_state.get("p1_pos", "?")
    p2_pos = game_state.get("p2_pos", "?")
    p1_walls = game_state.get("p1_walls", "?")
    p2_walls = game_state.get("p2_walls", "?")
    current_player = game_state.get("current_player", "?")

    # Create a short representation of placed walls, e.g., "WHC4,WVE6"
    walls_short = []
    for wall_str in game_state.get("placed_walls", []):
        parts = wall_str.split()
        if len(parts) == 3:
            # e.g., from "WALL H C4" -> "WHC4"
            walls_short.append(f"W{parts[1]}{parts[2]}")

    walls_log_str = ",".join(sorted(walls_short)) if walls_short else "[]"

    # P1 is the Bot, P2 is the Human
    return f"[G1/T{turn_num}] P{current_player} S(B:{p1_pos}({p1_walls}) H:{p2_pos}({p2_walls})|W:{walls_log_str})"

# --- Helper to Run Bot Turn ---
def run_bot_turn():
    """Finds and makes the Bot's move. Modifies the global 'game' object."""
    global game # The global game state is modified by this function

    if game.get_current_player() != BOT_PLAYER_ID:
        print(f"Error: run_bot_turn called when it is P{game.get_current_player()}'s turn.")
        return "Error: Not Bot's turn"

    print(f"{format_game_state_for_log(game.get_state_dict(), turn_count)} - Bot Turn Start")

    best_move = bot.find_best_move(game) # Bot's internal logging happens here

    status_message = f"P{BOT_PLAYER_ID}(Bot) Thinking..."

    if best_move:
        # Attempt to make the move chosen by the bot
        success, result = game.make_move(best_move)
        if success:
            status_message = f"P{BOT_PLAYER_ID}(Bot) OK: {best_move}"
            print(f"  OK: P{BOT_PLAYER_ID} played {best_move}")
            # The game logic in make_move handles switching the current player
        else:
            # This should ideally NOT happen if find_best_move guarantees validity
            reason_code = result
            status_message = f"P{BOT_PLAYER_ID}(Bot) ERR: Suggested {best_move} failed ({reason_code}) - Skipping!"
            print(f"!!CRITICAL FAILURE: Bot suggested invalid move '{best_move}'. Reason: {reason_code}. Skipping turn.")
            game.current_player = game.get_opponent(BOT_PLAYER_ID) # Manual skip to prevent game stall
    else:
        # Bot failed to find any move
        status_message = f"P{BOT_PLAYER_ID}(Bot) ERR: No valid moves found - Skipping!"
        print(f"!!CRITICAL FAILURE: Bot P{BOT_PLAYER_ID} found no valid moves. Skipping turn.")
        game.current_player = game.get_opponent(BOT_PLAYER_ID) # Manual skip

    return status_message

# --- Routes ---
@app.route('/')
def index():
    # Pass human player ID to template
    return render_template('index.html', board_size=BOARD_SIZE, human_player_id=HUMAN_PLAYER_ID)

@app.route('/start_game', methods=['POST'])
def start_game():
    global game, turn_count, game_active
    print("\n[LOG] ### GAME START ###")
    game = QuoridorGame()
    turn_count = 1
    game_active = True

    initial_state = game.get_state_dict()
    print(f"{format_game_state_for_log(initial_state, turn_count)} - Initial State")
    status_msg = "Game Started!"

    # If Bot is Player 1, it takes the first turn
    if initial_state.get('current_player') == BOT_PLAYER_ID:
        print("[LOG] Bot is Player 1, running initial turn...")
        status_msg = run_bot_turn() # This updates the global 'game' object
        final_state_after_bot = game.get_state_dict()
    else:
        final_state_after_bot = initial_state
        status_msg = "Game Started! Your turn (Player 2)."

    # Prepare and send the initial response
    response_state = final_state_after_bot
    response_state['status_message'] = status_msg
    response_state['turn_count'] = turn_count
    response_state['game_active'] = game_active
    response_state['human_player_id'] = HUMAN_PLAYER_ID
    return jsonify({"success": True, "message": status_msg, "game_state": response_state})

@app.route('/make_human_move', methods=['POST'])
def make_human_move():
    global game, turn_count, game_active

    if not game_active or game.is_game_over():
        return jsonify({"success": False, "reason": "Game is not active or is over.", "game_state": game.get_state_dict()})
    if game.get_current_player() != HUMAN_PLAYER_ID:
        return jsonify({"success": False, "reason": "It's not your turn.", "game_state": game.get_state_dict()})

    data = request.get_json()
    move_string = data.get('move')
    if not move_string:
        return jsonify({"success": False, "reason": "No move string provided.", "game_state": game.get_state_dict()})

    print(f"{format_game_state_for_log(game.get_state_dict(), turn_count)} - Human Recv: '{move_string}'")

    # Attempt to make the human's move
    success, result = game.make_move(move_string)

    if success:
        print(f"  OK: P{HUMAN_PLAYER_ID}(Human) played {move_string}")
        status_message = f"P{HUMAN_PLAYER_ID}(You) OK: {move_string}"
        reason = None # No failure reason

        # If the game isn't over after the human's move, trigger the bot's turn
        if not game.is_game_over():
            bot_status = run_bot_turn() # This updates the global 'game' object
            status_message = bot_status # The bot's status is now the primary message
            # Increment turn count ONLY after a full round (P2 Human, P1 Bot)
            turn_count += 1
        else:
            status_message = f"Game Over! Player {game.get_winner()}(You) Wins!"
            game_active = False
            print(f"[LOG] ### GAME OVER ### Winner: P{game.get_winner()} (Human)")
    else:
        # Human move failed
        reason_code = result
        print(f"  FAIL: P{HUMAN_PLAYER_ID}(Human) tried '{move_string}'. Reason: {reason_code}")
        status_message = f"Your Move Failed: '{move_string}' ({reason_code})"
        reason = reason_code

    # Check for a bot win after its potential turn
    if game.is_game_over() and game.get_winner() == BOT_PLAYER_ID:
        status_message = f"Game Over! Player {game.get_winner()}(Bot) Wins!"
        game_active = False
        print(f"[LOG] ### GAME OVER ### Winner: P{game.get_winner()} (Bot)")

    # Prepare and send the final response for this turn
    final_state = game.get_state_dict()
    final_state['status_message'] = status_message
    final_state['turn_count'] = turn_count
    final_state['game_active'] = game_active
    final_state['human_player_id'] = HUMAN_PLAYER_ID
    return jsonify({"success": success, "reason": reason, "game_state": final_state})

@app.route('/game_state')
def get_game_state_poll():
    """Endpoint for the client to poll for the latest game state."""
    global game_active, turn_count

    current_state = game.get_state_dict()
    current_state['turn_count'] = turn_count
    current_state['game_active'] = game_active
    current_state['human_player_id'] = HUMAN_PLAYER_ID

    # Determine the status message based on the game state
    if game.is_game_over():
        current_state['status_message'] = f"Game Over! Player {game.get_winner()} Wins!"
    elif not game_active:
        current_state['status_message'] = "Click 'Start Game' to begin."
    elif current_state['current_player'] == HUMAN_PLAYER_ID:
        current_state['status_message'] = f"Your turn (Player {HUMAN_PLAYER_ID})"
    else:
        current_state['status_message'] = f"Player {BOT_PLAYER_ID}(Bot) is thinking..."

    # Optional: Verbose logging for every poll request can be noisy.
    # print(f"-> Poll Snd: {format_game_state_for_log(current_state, turn_count)}")
    return jsonify(current_state)

if __name__ == '__main__':
    print("Starting Flask server Quoridor(Human vs AlgoBot)...")
    app.run(debug=False, host='0.0.0.0', port=25565)