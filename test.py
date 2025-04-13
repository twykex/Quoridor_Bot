import requests
import json
import re
import sys
import time # To add a small delay between API calls

# --- Configuration ---
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:12b"
# MODEL_NAME = "llama3"
# MODEL_NAME = "gemma:7b"
MAX_TURNS = 10 # Let's simulate 10 turns (5 for each player)

# --- Quoridor Constants ---
BOARD_SIZE = 9
INITIAL_WALLS = 10

# --- Prompt Engineering (Same as before) ---
def create_quoridor_prompt(player_pos, opponent_pos, player_walls, opponent_walls, walls_on_board, player_to_move):
    """Creates a detailed prompt for the LLM to generate a Quoridor move."""
    player_id = player_to_move
    opponent_id = 2 if player_to_move == 1 else 1
    player_goal_row = BOARD_SIZE if player_id == 1 else 1
    opponent_goal_row = BOARD_SIZE if opponent_id == 1 else 1

    prompt = f"""You are an expert AI playing the game of Quoridor.
Your goal is to reach the opposite side of the 9x9 board before your opponent.

Game Rules:
1. Board: 9x9 grid. Coordinates are like 'E1', 'A9', etc. Column (A-I), Row (1-9).
2. Players: Player 1 starts at E1, goal is row 9. Player 2 starts at E9, goal is row 1.
3. Turns: On your turn, you MUST choose one of the following actions:
    a. Move Pawn: Move your pawn one square orthogonally (up, down, left, right) to an adjacent empty square. Pawns cannot move diagonally. You cannot move into a square blocked by a wall. Jumping over an adjacent opponent pawn is allowed under specific rules (simplified for now, prioritize simple moves).
    b. Place Wall: Place a wall on the board edge lines. Walls are 2 squares long. They can be horizontal (H) or vertical (V). Walls block pawn movement. You have a limited number of walls.
4. Wall Placement Rules:
    - Walls occupy 2 cell edges. 'WALL H E1' blocks movement between E1-E2 and F1-F2. 'WALL V E1' blocks movement between E1-F1 and E2-F2. (Coordinate denotes the top-left square relative to the wall's placement center for API consistency).
    - Walls cannot overlap existing walls.
    - Crucially: Placing a wall MUST NOT completely block ALL possible paths for EITHER player to reach their respective goal rows.
5. Winning: The first player to reach any square on their opponent's starting row wins.

Your Task:
You are Player {player_id}. Analyze the current game state and decide on your next move (either move your pawn or place a wall).

Output Format Instructions:
*** CRITICAL: Respond ONLY with the move string, and nothing else. No explanations, no introductions, no apologies, no formatting like ```json ... ```. ***
- For moving the pawn: 'MOVE <coordinate>' (e.g., 'MOVE E2')
- For placing a horizontal wall: 'WALL H <coordinate>' (e.g., 'WALL H E5')
- For placing a vertical wall: 'WALL V <coordinate>' (e.g., 'WALL V E5')
   (Coordinate is the top-left square of the 2x2 block where the wall segment is placed, valid range A1-H8).

Current Game State:
- Board Size: {BOARD_SIZE}x{BOARD_SIZE}
- Your Position (Player {player_id}): {player_pos} (Goal: Row {player_goal_row})
- Opponent Position (Player {opponent_id}): {opponent_pos} (Goal: Row {opponent_goal_row})
- Your Walls Left: {player_walls}
- Opponent Walls Left: {opponent_walls}
- Walls currently on board: { 'None' if not walls_on_board else ', '.join(walls_on_board) }
- Player to Move: Player {player_id} (You)

Provide your next move:
"""
    return prompt

# --- Ollama API Interaction (Same as before) ---
def get_llm_move(prompt):
    """Sends the prompt to the Ollama API and returns the model's response."""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.5,
        }
    }
    headers = {'Content-Type': 'application/json'}

    print(f"\n--- Sending Prompt to Ollama ({MODEL_NAME}) ---")
    # print(prompt) # Keep commented unless debugging the prompt itself
    print("--------------------------------------------------")

    try:
        response = requests.post(OLLAMA_API_URL, headers=headers, json=payload, timeout=90) # Increased timeout
        response.raise_for_status()
        response_data = response.json()
        raw_response = response_data.get("response", "").strip()
        print(f"\n--- Raw Response from {MODEL_NAME} ---")
        print(raw_response)
        print("---------------------------------------")
        return raw_response
    except requests.exceptions.ConnectionError:
        print(f"\nError: Could not connect to Ollama API at {OLLAMA_API_URL}. Ensure Ollama is running.")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"\nError: Request to Ollama API timed out.")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"\nError interacting with Ollama API: {e}")
        try:
            print("Ollama Response Body:", response.text)
        except NameError: pass
        sys.exit(1)
    except json.JSONDecodeError:
        print("\nError: Could not decode JSON response from Ollama.")
        print("Raw Response Body:", response.text)
        sys.exit(1)

# --- Response Validation (Same as before) ---
def validate_move_format(move_string):
    """Checks if the move string matches the expected Quoridor move formats."""
    move_pattern = re.compile(r"^MOVE\s+([A-I])([1-9])$")
    wall_pattern = re.compile(r"^WALL\s+(H|V)\s+([A-H])([1-8])$") # A1-H8 for wall coords

    match_move = move_pattern.match(move_string)
    match_wall = wall_pattern.match(move_string)

    if match_move:
        col, row = match_move.groups()
        coord = f"{col}{row}"
        print(f"Validation: Detected valid format - PAWN MOVE to {coord}")
        return True, "MOVE", coord
    elif match_wall:
        orientation, col, row = match_wall.groups()
        coord = f"{col}{row}"
        wall_str = f"WALL {orientation} {coord}"
        print(f"Validation: Detected valid format - {wall_str}")
        return True, "WALL", (orientation, coord)
    else:
        print(f"Validation: Invalid format detected for response: '{move_string}'")
        return False, None, None

# --- Main Simulation Loop ---
if __name__ == "__main__":
    print("Starting Quoridor LLM Game Simulation...")

    # --- Initialize Game State ---
    game_state = {
        "p1_pos": "E1",
        "p2_pos": "E9",
        "p1_walls": INITIAL_WALLS,
        "p2_walls": INITIAL_WALLS,
        # MODIFICATION: Start with a wall blocking P1's direct path forward
        "board_walls": ["WALL H E1"],
        "current_player": 1,
        "turn": 1
    }
    # Notify user of the change
    print(f"INFO: Starting game with initial wall: {game_state['board_walls'][0]}")

    while game_state["turn"] <= MAX_TURNS:
        print(f"\n=============== TURN {game_state['turn']} : Player {game_state['current_player']} ================")

        # --- Prepare data for the prompt ---
        player_id = game_state["current_player"]
        if player_id == 1:
            player_pos = game_state["p1_pos"]
            opponent_pos = game_state["p2_pos"]
            player_walls = game_state["p1_walls"]
            opponent_walls = game_state["p2_walls"]
        else: # Player 2
            player_pos = game_state["p2_pos"]
            opponent_pos = game_state["p1_pos"]
            player_walls = game_state["p2_walls"]
            opponent_walls = game_state["p1_walls"]

        # --- Create Prompt and Get Move ---
        current_prompt = create_quoridor_prompt(
            player_pos=player_pos,
            opponent_pos=opponent_pos,
            player_walls=player_walls,
            opponent_walls=opponent_walls,
            walls_on_board=game_state["board_walls"],
            player_to_move=player_id
        )
        llm_response = get_llm_move(current_prompt)

        # --- Validate and Process Move ---
        if not llm_response:
            print("\nERROR: LLM returned an empty response. Stopping simulation.")
            break

        is_valid_format, move_type, details = validate_move_format(llm_response)

        if not is_valid_format:
            print(f"\nERROR: LLM response '{llm_response}' has invalid format. Stopping simulation.")
            break

        # --- Update Game State (SIMPLIFIED - NO LEGALITY CHECK) ---
        print(f"Player {player_id} attempts: {llm_response}")
        if move_type == "MOVE":
            new_pos = details
            # We STILL don't check if the move is legal (e.g., moving E1->E2 would be illegal here)
            # We just record what the LLM *attempted* based on the prompt
            if player_id == 1:
                game_state["p1_pos"] = new_pos
            else:
                game_state["p2_pos"] = new_pos
            print(f"State Update: Player {player_id} position changed to {new_pos}")

        elif move_type == "WALL":
            orientation, coord = details
            wall_string = f"WALL {orientation} {coord}"
            # Basic check: Does the player have walls left?
            # Basic check: Don't add duplicate walls (simplistic)
            if wall_string in game_state["board_walls"]:
                 print(f"WARNING: Player {player_id} tried to place wall '{wall_string}' which already exists! Ignoring move.")
                 continue # Skip to next turn without changing player

            if player_id == 1:
                if game_state["p1_walls"] > 0:
                    game_state["p1_walls"] -= 1
                    game_state["board_walls"].append(wall_string)
                    print(f"State Update: Player {player_id} placed {wall_string}. Walls left: {game_state['p1_walls']}")
                else:
                    print(f"WARNING: Player {player_id} tried to place wall '{wall_string}' but has no walls left! Ignoring move.")
            else: # Player 2
                if game_state["p2_walls"] > 0:
                    game_state["p2_walls"] -= 1
                    game_state["board_walls"].append(wall_string)
                    print(f"State Update: Player {player_id} placed {wall_string}. Walls left: {game_state['p2_walls']}")
                else:
                    print(f"WARNING: Player {player_id} tried to place wall '{wall_string}' but has no walls left! Ignoring move.")

        # --- Switch Player and Increment Turn ---
        game_state["current_player"] = 2 if player_id == 1 else 1
        game_state["turn"] += 1

        # --- Add delay ---
        time.sleep(1) # Be nice to the API, prevent rate limiting

    print(f"\n=============== SIMULATION END (After {game_state['turn']-1} turns) ===============")
    print("Final Game State:")
    print(f"  Player 1 Pos: {game_state['p1_pos']}, Walls Left: {game_state['p1_walls']}")
    print(f"  Player 2 Pos: {game_state['p2_pos']}, Walls Left: {game_state['p2_walls']}")
    print(f"  Walls on Board: {', '.join(game_state['board_walls']) if game_state['board_walls'] else 'None'}")