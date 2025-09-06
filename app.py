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
game = QuoridorGame(num_players=4)
turn_count = 1
game_active = False
HUMAN_PLAYER_ID = 1
BOT_PLAYER_IDS = [2, 3, 4]
BOT_SEARCH_DEPTH = 3
bots = {p_id: QuoridorBot(player_id=p_id, search_depth=BOT_SEARCH_DEPTH) for p_id in BOT_PLAYER_IDS}


# --- Compact Console Logging Helper ---
def fss(game_state, turn_num):
    cp = game_state.get("current_player", "?")
    pawn_pos_str = ", ".join([f"P{p}:{pos}" for p, pos in game_state.get("pawn_positions", {}).items()])
    walls_left_str = ", ".join([f"P{p}:{w}" for p, w in game_state.get("walls_left", {}).items()])
    walls_short = [f"W{p[1]}{p[2]}" for w in game_state.get("placed_walls", []) if len(p := w.split()) == 3]
    walls_str = ",".join(sorted(walls_short)) if walls_short else "[]"
    return f"[G1/T{turn_num}] P{cp} S({pawn_pos_str} | {walls_left_str} | W:{walls_str})"

# --- Helper to Run Bot Turn ---
def run_bot_turn(bot_player_id):
    """Finds and makes the Bot's move. Modifies global 'game'."""
    global game, turn_count

    if game.current_player != bot_player_id:
        print(f"Error: run_bot_turn called for P{bot_player_id} but it is P{game.current_player}'s turn.")
        return f"Error: Not P{bot_player_id}'s turn"

    bot = bots[bot_player_id]
    print(f"{fss(game.get_state_dict(), turn_count)} - P{bot_player_id}(Bot) Turn Start")

    best_move = bot.find_best_move(game)
    status_message = f"P{bot_player_id}(Bot) Thinking..."

    if best_move:
        success, reason_code = game.make_move(best_move)
        if success:
            status_message = f"P{bot_player_id}(Bot) OK: {best_move}"
            print(f"  OK: P{bot_player_id} ply {best_move}")
            if game.is_game_over():
                status_message = f"G Over! P{game.winner}(Bot) Wins!"
        else:
            status_message = f"P{bot_player_id}(Bot) ERR: Sug. {best_move} Fail({reason_code}) - Skipping!"
            print(f"!!CRIT F: Bot suggested invalid move '{best_move}' Rsn:{reason_code}. Skipping.")
            game.current_player = game._get_next_player()
    else:
        status_message = f"P{bot_player_id}(Bot) ERR: No valid moves found - Skipping!"
        print(f"!!CRIT F: Bot P{bot_player_id} found no moves. Skipping.")
        game.current_player = game._get_next_player()

    if game.current_player == HUMAN_PLAYER_ID:
        turn_count +=1

    return status_message

def run_bot_turns():
    """Runs turns for all bots until it is the human's turn again."""
    global game
    status_message = "Bots are playing..."
    while game.current_player != HUMAN_PLAYER_ID and not game.is_game_over():
        bot_id = game.current_player
        status_message = run_bot_turn(bot_id)
        # Add a small delay to make the bots' moves visible on the frontend
        time.sleep(0.5)
    return status_message

# --- Routes ---
@app.route('/')
def index():
    # Pass human player ID to template
    return render_template('index.html', board_size=BOARD_SIZE, human_player_id=HUMAN_PLAYER_ID)

@app.route('/start_game', methods=['POST'])
def start_game():
    global game, turn_count, game_active, bots
    print("\n[LOG] ### G START ###")
    game = QuoridorGame(num_players=4)
    bots = {p_id: QuoridorBot(player_id=p_id, search_depth=BOT_SEARCH_DEPTH) for p_id in BOT_PLAYER_IDS}
    turn_count = 1
    game_active = True
    initial_state = game.get_state_dict()
    print(f"{fss(initial_state, turn_count)} - Init State")
    status_msg = "Game Started! Your turn (P1)."

    response_state = initial_state
    response_state['status_message'] = status_msg
    response_state['turn_count'] = turn_count
    response_state['game_active'] = game_active
    response_state['human_player_id'] = HUMAN_PLAYER_ID
    return jsonify({"success": True, "message": status_msg, "game_state": response_state})

@app.route('/make_human_move', methods=['POST'])
def make_human_move():
    global game, turn_count, game_active
    success = False
    reason = "Invalid request"
    status_message = "Error"

    if not game_active or game.is_game_over():
        reason = "G Inactive/Over"
        return jsonify({"success": False, "reason": reason, "game_state": game.get_state_dict()})
    if game.current_player != HUMAN_PLAYER_ID:
        reason = "Not Your Turn"
        return jsonify({"success": False, "reason": reason, "game_state": game.get_state_dict()})

    data = request.get_json()
    move_string = data.get('move')
    if not move_string:
        reason = "No Move"
        return jsonify({"success": False, "reason": reason, "game_state": game.get_state_dict()})

    print(f"{fss(game.get_state_dict(), turn_count)} - H Recv: '{move_string}'")

    success, reason_code = game.make_move(move_string)

    if success:
        print(f"  OK P{HUMAN_PLAYER_ID}(H) ply {move_string}")
        status_message = f"P{HUMAN_PLAYER_ID}(You) OK: {move_string}"
        reason = None
        if not game.is_game_over():
            status_message = run_bot_turns()
        else:
            status_message = f"G Over! P{game.winner}(You) Wins!"
            game_active = False
            print(f"[LOG] ### G OVER ### W: P{game.winner} H")
    else:
        print(f"  F P{HUMAN_PLAYER_ID}(H) try '{move_string}'. R:{reason_code}")
        status_message = f"Your Move F: '{move_string}' ({reason_code})"
        reason = reason_code

    if game.is_game_over() and game.winner in BOT_PLAYER_IDS:
        status_message = f"G Over! P{game.winner}(Bot) Wins!"
        game_active = False
        print(f"[LOG] ### G OVER ### W: P{game.winner} B")

    final_state = game.get_state_dict()
    final_state['status_message'] = status_message
    final_state['turn_count'] = turn_count
    final_state['game_active'] = game_active
    final_state['human_player_id'] = HUMAN_PLAYER_ID
    return jsonify({"success": success, "reason": reason, "game_state": final_state})

@app.route('/game_state') # Polling endpoint
def get_game_state_poll():
    global game_active, turn_count
    cs = game.get_state_dict()
    cs['turn_count'] = turn_count
    cs['game_active'] = game_active
    cs['human_player_id'] = HUMAN_PLAYER_ID
    if game.is_game_over():
        cs['status_message'] = f"G Over! P{game.winner} Wins!"
    elif not game_active:
        cs['status_message'] = "Click Start"
    elif cs['current_player'] == HUMAN_PLAYER_ID:
        cs['status_message'] = f"Your turn(P{HUMAN_PLAYER_ID})"
    else:
        cs['status_message'] = f"P{game.current_player}(Bot) Thinking..."
    return jsonify(cs)

if __name__ == '__main__':
    print("Starting Flask server Quoridor(Human vs AlgoBot)...")
    app.run(debug=False, host='0.0.0.0', port=8123)