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
def fss(game_state, turn_num): # format_state_short abbreviated
    p1p=game_state.get("p1_pos", "?"); p2p=game_state.get("p2_pos", "?")
    p1w=game_state.get("p1_walls", "?"); p2w=game_state.get("p2_walls", "?")
    cp=game_state.get("current_player", "?")
    walls_short=[f"W{p[1]}{p[2]}" for w in game_state.get("placed_walls", []) if len(p := w.split()) == 3]
    walls_str=",".join(sorted(walls_short)) if walls_short else "[]"
    # P1=Bot, P2=Human
    return f"[G1/T{turn_num}] P{cp} S(B:{p1p}({p1w}) H:{p2p}({p2w})|W:{walls_str})" # B=Bot, H=Human

# --- Helper to Run Bot Turn ---
def run_bot_turn():
    """Finds and makes the Bot's move. Modifies global 'game'."""
    global game # Need to modify the global game state

    if game.current_player != BOT_PLAYER_ID:
        print(f"Error: run_bot_turn called when it is P{game.current_player}'s turn.")
        return "Error: Not Bot's turn"

    print(f"{fss(game.get_state_dict(), turn_count)} - Bot Turn Start")

    # Find the best move using the bot's algorithm
    # Pass a copy of the game state to find_best_move if it modifies it internally for safety
    # but current find_best_move uses deepcopy internally for simulations
    best_move = bot.find_best_move(game) # Bot internal logging happens here

    status_message = f"P{BOT_PLAYER_ID}(Bot) Thinking..." # Default
    move_played = None

    if best_move:
        # Attempt to make the move chosen by the bot
        success, reason_code = game.make_move(best_move)
        if success:
            move_played = best_move
            status_message = f"P{BOT_PLAYER_ID}(Bot) OK: {best_move}"
            print(f"  OK: P{BOT_PLAYER_ID} ply {best_move}")
            # Player is switched by make_move
        else:
            # This should ideally NOT happen if find_best_move guarantees validity
            status_message = f"P{BOT_PLAYER_ID}(Bot) ERR: Sug. {best_move} Fail({reason_code}) - Skipping!"
            print(f"!!CRIT F: Bot suggested invalid move '{best_move}' Rsn:{reason_code}. Skipping.")
            game.current_player = game.get_opponent(BOT_PLAYER_ID) # Manual skip
    else:
        # Bot failed to find any move
        status_message = f"P{BOT_PLAYER_ID}(Bot) ERR: No valid moves found - Skipping!"
        print(f"!!CRIT F: Bot P{BOT_PLAYER_ID} found no moves. Skipping.")
        game.current_player = game.get_opponent(BOT_PLAYER_ID) # Manual skip

    return status_message # Return status string

# --- Routes ---
@app.route('/')
def index():
    # Pass human player ID to template
    return render_template('index.html', board_size=BOARD_SIZE, human_player_id=HUMAN_PLAYER_ID)

@app.route('/start_game', methods=['POST'])
def start_game():
    global game, turn_count, game_active
    print("\n[LOG] ### G START ###")
    game = QuoridorGame(); turn_count = 1; game_active = True
    initial_state = game.get_state_dict(); print(f"{fss(initial_state, turn_count)} - Init State")
    status_msg = "Game Started!"

    # If Bot starts (P1), run its first turn
    if initial_state.get('current_player') == BOT_PLAYER_ID:
         print("[LOG] Init Bot Turn...")
         status_msg = run_bot_turn() # Run bot turn, updates global 'game'
         final_state_after_bot = game.get_state_dict()
    else:
         final_state_after_bot = initial_state
         status_msg = "Game Started! Your turn(P2)."

    response_state = final_state_after_bot; response_state['status_message'] = status_msg
    response_state['turn_count'] = turn_count; response_state['game_active'] = game_active
    response_state['human_player_id'] = HUMAN_PLAYER_ID
    return jsonify({"success": True, "message": status_msg, "game_state": response_state})

@app.route('/make_human_move', methods=['POST'])
def make_human_move():
    global game, turn_count, game_active
    success = False; reason = "Invalid request"; status_message = "Error"

    if not game_active or game.is_game_over(): reason = "G Inactive/Over"; return jsonify({"success": False, "reason": reason, "game_state": game.get_state_dict()})
    if game.current_player != HUMAN_PLAYER_ID: reason = "Not Your Turn"; return jsonify({"success": False, "reason": reason, "game_state": game.get_state_dict()})

    data = request.get_json(); move_string = data.get('move')
    if not move_string: reason = "No Move"; return jsonify({"success": False, "reason": reason, "game_state": game.get_state_dict()})

    print(f"{fss(game.get_state_dict(), turn_count)} - H Recv: '{move_string}'")

    # Attempt human move
    success, reason_code = game.make_move(move_string)

    if success:
        print(f"  OK P{HUMAN_PLAYER_ID}(H) ply {move_string}")
        status_message = f"P{HUMAN_PLAYER_ID}(You) OK: {move_string}"
        reason = None
        # Human move OK, trigger Bot turn if game not over
        if not game.is_game_over():
             # It is now Bot's turn (make_move switched player)
             bot_status = run_bot_turn() # Run bot turn, updates global 'game'
             status_message = bot_status # Report Bot's status
             # Increment turn count AFTER P2(H) moves AND P1(B) responds
             turn_count += 1
        else: # Human won
             status_message = f"G Over! P{game.winner}(You) Wins!"; game_active = False
             print(f"[LOG] ### G OVER ### W: P{game.winner} H")
    else: # Human move failed
        print(f"  F P{HUMAN_PLAYER_ID}(H) try '{move_string}'. R:{reason_code}")
        status_message = f"Your Move F: '{move_string}' ({reason_code})"; reason = reason_code

    # Check for Bot win after its potential turn
    if game.is_game_over() and game.winner == BOT_PLAYER_ID:
        status_message = f"G Over! P{game.winner}(Bot) Wins!"; game_active = False
        print(f"[LOG] ### G OVER ### W: P{game.winner} B")

    final_state = game.get_state_dict(); final_state['status_message'] = status_message; final_state['turn_count'] = turn_count
    final_state['game_active'] = game_active; final_state['human_player_id'] = HUMAN_PLAYER_ID
    return jsonify({"success": success, "reason": reason, "game_state": final_state})

@app.route('/game_state') # Polling endpoint
def get_game_state_poll():
    global game_active, turn_count
    cs = game.get_state_dict(); cs['turn_count'] = turn_count
    cs['game_active'] = game_active; cs['human_player_id'] = HUMAN_PLAYER_ID
    if game.is_game_over(): cs['status_message'] = f"G Over! P{game.winner} Wins!"
    elif not game_active: cs['status_message'] = "Click Start"
    elif cs['current_player'] == HUMAN_PLAYER_ID: cs['status_message'] = f"Your turn(P{HUMAN_PLAYER_ID})"
    else: cs['status_message'] = f"P{BOT_PLAYER_ID}(Bot) Thinking..." # Status while Bot turn is pending user action
    # print(f"-> Poll Snd: {fss(cs, turn_count)}") # Optional verbose polling log
    return jsonify(cs)

if __name__ == '__main__':
    print("Starting Flask server Quoridor(Human vs AlgoBot)...")
    app.run(debug=False, host='0.0.0.0', port=25565)