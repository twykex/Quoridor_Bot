# test_wall_prompt.py

import sys

try:
    from ollama_interface import create_quoridor_prompt, get_llm_move, validate_move_format
    from quoridor_logic import INITIAL_WALLS, BOARD_SIZE # Import constants if needed
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Ensure quoridor_logic.py and ollama_interface.py are in the same directory.")
    sys.exit(1)

def run_test(test_state, description):
    """Runs a single test case."""
    print(f"\n===== TESTING SCENARIO: {description} =====")
    print(f"State: P1@{test_state['p1_pos']}, P2@{test_state['p2_pos']}, Player {test_state['current_player']} to move")
    print(f"(P1 GoalRow: {BOARD_SIZE-1}, P2 GoalRow: 0)")
    print("---------------------------------------------")

    prompt = create_quoridor_prompt(test_state)
    llm_response = get_llm_move(prompt)

    if not llm_response:
        print("RESULT: FAILED - LLM did not return a response.")
        return False, None

    is_valid_fmt = validate_move_format(llm_response)
    if not is_valid_fmt:
         print("RESULT: FAILED - LLM response has invalid format.")
         return False, llm_response

    return True, llm_response

# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Defensive Wall Prompt Test...")

    # --- Test Case 1: P2 should place a wall ---
    # P1 is significantly closer to goal (Row 9) than P2 is to their goal (Row 1)
    state_p2_defend = {
        "board_size": BOARD_SIZE,
        "p1_pos": "E7", # P1 needs 2 more rows (Dist=2)
        "p2_pos": "E5", # P2 needs 5 more rows (Dist=5)
        "p1_walls": 8,
        "p2_walls": 8,
        "placed_walls": [], # Empty board for simplicity
        "current_player": 2, # Player 2 (further away) to move
        "winner": None,
        "is_game_over": False
    }
    success1, response1 = run_test(state_p2_defend, "P1@E7, P2@E5. P2 to move (should defend)")

    if success1:
        if response1.startswith("WALL"):
            print(f"RESULT: PASSED - LLM suggested a WALL command: '{response1}'")
        else:
            print(f"RESULT: FAILED (Expected Wall) - LLM suggested a MOVE: '{response1}'")

    # --- Test Case 2: P1 should place a wall ---
    # P2 is significantly closer to goal (Row 1) than P1 is to their goal (Row 9)
    state_p1_defend = {
        "board_size": BOARD_SIZE,
        "p1_pos": "E5", # P1 needs 4 more rows (Dist=4)
        "p2_pos": "E2", # P2 needs 2 more rows (Dist=2)
        "p1_walls": 7,
        "p2_walls": 7,
        "placed_walls": ["WALL H F7"], # Add a random wall
        "current_player": 1, # Player 1 (further away) to move
        "winner": None,
        "is_game_over": False
    }
    success2, response2 = run_test(state_p1_defend, "P1@E5, P2@E2. P1 to move (should defend)")

    if success2:
        if response2.startswith("WALL"):
            print(f"RESULT: PASSED - LLM suggested a WALL command: '{response2}'")
        else:
            print(f"RESULT: FAILED (Expected Wall) - LLM suggested a MOVE: '{response2}'")

    # --- Test Case 3: Distances are equal, should likely move ---
    state_equal = {
        "board_size": BOARD_SIZE,
        "p1_pos": "E4", # P1 needs 5 rows (Dist=5)
        "p2_pos": "E5", # P2 needs 5 rows (Dist=5)
        "p1_walls": 6,
        "p2_walls": 6,
        "placed_walls": [],
        "current_player": 1,
        "winner": None,
        "is_game_over": False
    }
    success3, response3 = run_test(state_equal, "P1@E4, P2@E5. P1 to move (likely move)")

    if success3:
        if response3.startswith("MOVE"):
            print(f"RESULT: PASSED (Expected Move) - LLM suggested: '{response3}'")
        else:
            print(f"RESULT: FAILED (Expected Move) - LLM suggested WALL: '{response3}'")


    print("\n===== DEFENSIVE WALL TESTING COMPLETE =====")