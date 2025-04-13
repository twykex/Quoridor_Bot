# main_console.py (LLM vs LLM Simulation Mode - Fix NameError)

import time
import sys
import random

try:
    from quoridor_logic import QuoridorGame, BOARD_SIZE
    from ollama_interface import create_quoridor_prompt, get_llm_move, validate_move_format
except ImportError as e:
    print(f"!!ImportErr: {e}")
    sys.exit(1)

# --- Configuration ---
MAX_GAMES = 10
MAX_TURNS_PER_GAME = 150
MOVE_DELAY_SEC = 0.0
MAX_RETRIES_PER_TURN = 1

# --- Global Game State (for simulation) ---
game = QuoridorGame() # Initialize once, reset per game
game_num = 0
turn_count = 1
last_llm_failure_reason = None # Track P1 failure across turns

# --- Compact Console Logging Helper ---
def fss(game_state, turn_num): # format_state_short abbreviated
    p1p=game_state.get("p1_pos", "?"); p2p=game_state.get("p2_pos", "?")
    p1w=game_state.get("p1_walls", "?"); p2w=game_state.get("p2_walls", "?")
    cp=game_state.get("current_player", "?")
    walls_short=[f"W{p[1]}{p[2]}" for w in game_state.get("placed_walls", []) if len(p := w.split()) == 3]
    walls_str=",".join(sorted(walls_short)) if walls_short else "[]"
    return f"[G{game_num}/T{turn_num}] P{cp} S(A:{p1p}({p1w}) B:{p2p}({p2w})|W:{walls_str})"

# --- Helper to Run LLM Turn ---
def run_llm_simulation_turn(current_game_obj: QuoridorGame, game_num: int, turn_num: int):
    """Handles one LLM turn within simulation, modifies the passed game object."""
    # --- FIX: Declare global variable ---
    global last_llm_failure_reason
    # --- End FIX ---

    player_id = current_game_obj.current_player
    current_game_state_dict = current_game_obj.get_state_dict()

    print(f"{fss(current_game_state_dict, turn_num)}") # Log start state

    final_move_success = False; llm_move_attempted = None
    current_turn_fail_reason = None
    # Use persistent reason only if it's P1's turn and a reason exists from P1's last fail
    prompt_fail_reason = last_llm_failure_reason if player_id == 1 else None
    if player_id == 1: last_llm_failure_reason = None # Reset for P1's next turn cycle

    for attempt in range(1, 1 + MAX_RETRIES_PER_TURN + 1):
        print(f"  P{player_id} A{attempt}...")

        prompt = None; valid_pawns_coords=None; valid_walls_strings=None
        if current_turn_fail_reason: # Retry
            # print(f"  Calc valid M retry(R:{current_turn_fail_reason})...")
            try:
                valid_pawn_tuples = current_game_obj.get_valid_pawn_moves(player_id)
                valid_pawns_coords = sorted([current_game_obj._pos_to_coord(p) for p in valid_pawn_tuples])
                valid_walls_strings = current_game_obj.get_valid_wall_placements(player_id)
                # print(f"  Retry: Fnd {len(valid_pawns_coords)}p/{len(valid_walls_strings)}w valid M.")
                prompt = create_quoridor_prompt(current_game_state_dict,
                                               last_move_fail_reason=current_turn_fail_reason,
                                               valid_pawn_moves_list=valid_pawns_coords,
                                               valid_wall_placements_list=valid_walls_strings)
            except Exception as e:
                print(f"!!ERR Calc valid M: {e}"); current_turn_fail_reason = "ValidMoveCalcErr"; break
        else: # First attempt
            prompt = create_quoridor_prompt(current_game_state_dict, last_move_fail_reason=prompt_fail_reason)

        if prompt is None: current_turn_fail_reason = "PromptErr"; break

        llm_move = get_llm_move(prompt)
        llm_move_attempted = llm_move

        if not llm_move:
            print(f"  F A{attempt}: P{player_id} API Err/Empty.")
            current_turn_fail_reason = "API Err"
            if attempt >= (1 + MAX_RETRIES_PER_TURN): break; continue
        elif not validate_move_format(llm_move):
            print(f"  F A{attempt}: P{player_id} Fmt Err '{llm_move}'.")
            current_turn_fail_reason = "Fmt Err"
            if attempt >= (1 + MAX_RETRIES_PER_TURN): break; continue
        else:
            # Use the 'game' object passed into the function
            success, reason_code = current_game_obj.make_move(llm_move)
            if success:
                print(f"  OK A{attempt}: P{player_id} ply {llm_move}")
                final_move_success = True
                if player_id == 1: last_llm_failure_reason = None # Clear persistent P1 reason
                break
            else:
                print(f"  F A{attempt}: P{player_id} try '{llm_move}'. R:{reason_code}")
                current_turn_fail_reason = reason_code
                if player_id == 1: last_llm_failure_reason = reason_code # Store persistent P1 reason
                if attempt >= (1 + MAX_RETRIES_PER_TURN): break

    if not final_move_success:
        print(f"!!CRIT F: P{player_id} fail A{attempt} (Last:{current_turn_fail_reason})-Skip.")
        current_game_obj.current_player = current_game_obj.get_opponent(player_id) # Manually skip

    # No return needed as it modifies the game object directly

# --- Main Simulation Loop ---
def run_simulations():
    global turn_count, game, game_num # Need access to modify these globals

    total_wins = {1: 0, 2: 0}
    total_turns = 0
    start_time_all = time.time()

    for G in range(1, MAX_GAMES + 1):
        game_num = G
        game = QuoridorGame() # Reset game object for new game
        turn_count = 1
        last_llm_failure_reason = None # Reset persistent reason for P1
        print(f"\n\n=== STARTING GAME {game_num} ===")

        while turn_count <= MAX_TURNS_PER_GAME:
            if game.is_game_over():
                winner = game.get_winner()
                print(f"[G{game_num}/T{turn_count-1}] ### G OVER ### W: P{winner}")
                total_wins[winner] += 1
                total_turns += (turn_count -1)
                break

            # Run turn for current player - modifies 'game' object
            run_llm_simulation_turn(game, game_num, turn_count)

            if game.is_game_over(): # Check again in case the last move ended it
                 winner = game.get_winner()
                 if winner is not None: # Ensure winner is set before logging
                     print(f"[G{game_num}/T{turn_count}] ### G OVER ### W: P{winner}")
                     # Avoid double counting if already broken above
                     if winner not in total_wins or total_wins[winner] == (G - sum(total_wins.values()) -1):
                         total_wins[winner] += 1
                         total_turns += turn_count
                 break

            # Increment turn count logic needs careful review
            # If P1 just moved (successfully or skipped), it becomes P2's turn (handled by make_move/skip)
            # If P2 just moved (successfully or skipped), it becomes P1's turn AND turn count increases
            if game.current_player == 1: # If it's now P1's turn, P2 must have just finished
                 turn_count += 1

            if MOVE_DELAY_SEC > 0: time.sleep(MOVE_DELAY_SEC)

        if turn_count > MAX_TURNS_PER_GAME and not game.is_game_over(): # Check if max turns reached without win
            print(f"[G{game_num}] ### MAX TURNS REACHED ({MAX_TURNS_PER_GAME}) ###")
            total_turns += MAX_TURNS_PER_GAME

    end_time_all = time.time()
    print("\n\n=== SIMULATION SUMMARY ===")
    print(f"Games Played: {MAX_GAMES}"); print(f"P1 Wins: {total_wins[1]} ({total_wins[1]/max(1,MAX_GAMES)*100:.1f}%)")
    print(f"P2 Wins: {total_wins[2]} ({total_wins[2]/max(1,MAX_GAMES)*100:.1f}%)"); print(f"Avg Turns/Game: {total_turns / max(1,MAX_GAMES):.1f}")
    print(f"Total Time: {end_time_all - start_time_all:.2f} seconds")

if __name__ == "__main__": run_simulations()