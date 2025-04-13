# test_adjacent_prompt.py

import sys

try:
    from ollama_interface import create_quoridor_prompt, get_llm_move, validate_move_format
    # Make sure quoridor_logic.py is available for constants if needed, though not directly used here
    from quoridor_logic import INITIAL_WALLS, BOARD_SIZE
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Ensure quoridor_logic.py and ollama_interface.py are in the same directory.")
    sys.exit(1)

def test_specific_state(test_state, test_description):
    """Creates prompt, gets LLM move, and validates format for a given state."""
    print(f"\n===== TESTING SCENARIO: {test_description} =====")
    print(f"State: P1@{test_state['p1_pos']}, P2@{test_state['p2_pos']}, Player {test_state['current_player']} to move")
    print(f"Walls: {test_state['placed_walls']}")
    print("---------------------------------------------")

    prompt = create_quoridor_prompt(test_state)
    llm_response = get_llm_move(prompt)

    if not llm_response:
        print("RESULT: FAILED - LLM did not return a response.")
        return False

    is_valid_fmt = validate_move_format(llm_response)
    if not is_valid_fmt:
         print("RESULT: FAILED - LLM response has invalid format.")
         return False

    # Basic check if the move is the known ILLEGAL one
    illegal_move_p1 = "MOVE E9" if test_state['p1_pos'] == 'E8' and test_state['p2_pos'] == 'E9' else None
    illegal_move_p2 = "MOVE E1" if test_state['p2_pos'] == 'E2' and test_state['p1_pos'] == 'E1' else None # Example symmetric case
    illegal_move_p2_specific = "MOVE E8" if test_state['p2_pos'] == 'E9' and test_state['p1_pos'] == 'E8' else None


    if test_state['current_player'] == 1 and llm_response == illegal_move_p1:
         print(f"RESULT: FAILED - LLM suggested the illegal move '{illegal_move_p1}'.")
         return False
    elif test_state['current_player'] == 2 and llm_response == illegal_move_p2_specific:
         print(f"RESULT: FAILED - LLM suggested the illegal move '{illegal_move_p2_specific}'.")
         return False
    # Add other specific illegal checks if needed

    print(f"RESULT: PASSED - LLM suggested '{llm_response}' (Format OK, not the obvious illegal move).")
    print("(Full legality requires game engine check)")
    return True


# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Adjacent Pawn Prompt Test...")

    # --- Test Case 1: P1 blocked by P2 ---
    state_p1_blocked = {
        "board_size": BOARD_SIZE,
        "p1_pos": "E8",
        "p2_pos": "E9",
        "p1_walls": 8, # Example wall counts
        "p2_walls": 7,
        "placed_walls": ["WALL H A1", "WALL V H7"], # Example walls, away from blockage
        "current_player": 1, # Player 1 to move
        "winner": None,
        "is_game_over": False
    }
    test_specific_state(state_p1_blocked, "P1 at E8, P2 at E9, P1 to move")


    # --- Test Case 2: P2 blocked by P1 ---
    state_p2_blocked = {
        "board_size": BOARD_SIZE,
        "p1_pos": "E8", # Same positions
        "p2_pos": "E9",
        "p1_walls": 8,
        "p2_walls": 7,
        "placed_walls": ["WALL H A1", "WALL V H7"],
        "current_player": 2, # Player 2 to move
        "winner": None,
        "is_game_over": False
    }
    test_specific_state(state_p2_blocked, "P1 at E8, P2 at E9, P2 to move")

    # --- Optional Test Case 3: Different location ---
    state_mid_block = {
        "board_size": BOARD_SIZE,
        "p1_pos": "D4",
        "p2_pos": "D5",
        "p1_walls": 5,
        "p2_walls": 5,
        "placed_walls": [],
        "current_player": 1, # Player 1 to move
        "winner": None,
        "is_game_over": False
    }
    # test_specific_state(state_mid_block, "P1 at D4, P2 at D5, P1 to move") # Uncomment to run

    print("\n===== TESTING COMPLETE =====")