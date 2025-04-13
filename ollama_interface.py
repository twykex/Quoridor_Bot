# ollama_interface.py (Readable Format - Final Strategy Refinements)

import requests
import json
import re
import sys
import math

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:27b" # Using the 27b model

# --- Prompt Engineering (REFINED - Strategy, Own Path, Endgame Focus) ---
# Add parameters for valid move lists and failure reason
def create_quoridor_prompt(game_state_dict, last_move_fail_reason=None,
                           valid_pawn_moves_list=None, valid_wall_placements_list=None):
    """
    Creates prompt focusing on better strategy, esp. wall placement & endgame.
    Includes optional lists of valid moves for retry attempts.
    """
    # --- Setup ---
    player_id = game_state_dict["current_player"]; opponent_id = 2 if player_id == 1 else 1; board_size = game_state_dict["board_size"]

    # Helper function to get 0-indexed row from coordinate string (e.g., 'E7' -> 6)
    def get_row_from_coord(coord_str):
        if not coord_str or len(coord_str) < 2: return -1
        try: return int(coord_str[1:]) - 1
        except ValueError: return -1

    player_goal_row_idx = board_size - 1 if player_id == 1 else 0
    opponent_goal_row_idx = 0 if player_id == 1 else board_size - 1

    # Get positions and calculate row indices using .get for safety
    if player_id == 1: p_pos, o_pos = game_state_dict.get("p1_pos","?"), game_state_dict.get("p2_pos","?"); p_walls, o_walls = game_state_dict.get("p1_walls",0), game_state_dict.get("p2_walls",0)
    else: p_pos, o_pos = game_state_dict.get("p2_pos","?"), game_state_dict.get("p1_pos","?"); p_walls, o_walls = game_state_dict.get("p2_walls",0), game_state_dict.get("p1_walls",0)

    p_row_idx = get_row_from_coord(p_pos); o_row_idx = get_row_from_coord(o_pos)
    walls_list = game_state_dict.get("placed_walls",[]); walls_str = ', '.join(walls_list) if walls_list else 'None'
    p_dist = abs(p_row_idx - player_goal_row_idx) if p_row_idx != -1 else 999; o_dist = abs(o_row_idx - opponent_goal_row_idx) if o_row_idx != -1 else 999
    defense_trigger = (o_dist <= p_dist - 1 and o_dist <= math.ceil(board_size / 2) - 1 and p_walls > 0)
    is_endgame = (p_walls == 0)
    # --- End Setup ---

    # --- Add Previous Failure Info ---
    failure_info = ""
    if last_move_fail_reason: failure_info = f"\n\n!! PREVIOUS FAILED (Rsn: {last_move_fail_reason})! Choose DIFFERENT VALID move from lists below. Check rules/reason. !!"

    # --- Add Valid Move Lists & Selection Guidance (if provided on retry) ---
    valid_moves_section = ""; is_retry_prompt = valid_pawn_moves_list is not None or valid_wall_placements_list is not None
    retry_selection_guidance = ""
    if is_retry_prompt:
        valid_moves_section = "\n\n**VALID MOVES (Choose ONLY from lists):**"
        pawn_moves_str_list = [];
        if valid_pawn_moves_list is not None:
            pawn_moves_str_list = [f"MOVE {c}" for c in valid_pawn_moves_list]
            valid_moves_section += f"\n- Pawn: {', '.join(pawn_moves_str_list) if pawn_moves_str_list else 'None'}"
        else:
            valid_moves_section += "\n- Pawn: None"

        wall_list_str_display = 'None'
        if valid_wall_placements_list is not None:
            if valid_wall_placements_list:
                max_walls=25; disp=valid_wall_placements_list[:max_walls]; wall_list_str_display=', '.join(disp)
                if len(valid_wall_placements_list)>max_walls: wall_list_str_display+=f",...({len(valid_wall_placements_list)-max_walls} more)"
            valid_moves_section += f"\n- Walls: {wall_list_str_display}"
        else:
             valid_moves_section += "\n- Walls: None" # Indicate if list wasn't provided

        retry_selection_guidance = """
**RETRY STRATEGY:**
1.  **Best Pawn Move:** Choose `MOVE <Coord>` closest to Goal Row {p_goal_idx_fmt}.
2.  **Best Wall (If needed):** If no good pawn move, choose BEST wall (hinders {o_pos} near them, safe for you {p_pos}).
**MUST CHOOSE ONE VALID MOVE FROM ABOVE.**""".format(p_goal_idx_fmt=player_goal_row_idx+1, o_pos=o_pos, p_pos=p_pos)
        valid_moves_section += retry_selection_guidance
    # --- End Valid Move Section ---

    initial_attempt_header = "**INITIAL ATTEMPT STRATEGY:**" if not is_retry_prompt else ""

    # --- Build the Prompt ---
    prompt = f"""You are an expert Quoridor AI. Priority: VALIDITY >> PROGRESSION >> HINDRANCE. {failure_info} {valid_moves_section}

{initial_attempt_header}
Rules Summary & Validation: (Apply if not given list)
- Pawn: 1 Orthogonal step (empty). No walls. Jumps if adj. Cannot land on Opponent ({o_pos}). Check walls [{walls_str}].
- Wall: 'WALL H/V Crd'(A1-H8). Check Rules: A(Overlap), B(Crossing), C(Adjacent Parallel) vs [{walls_str}]. No Path Blocking. **CHECK RULE C!**

**STRATEGIC GUIDANCE (CRITICAL DECISION FLOW):**

1.  **VALIDATE FIRST:** Always mentally check ALL rules. Invalid moves lose.

2.  **ENDGAME CHECK ({is_endgame}):** If TRUE (0 walls), Choose BEST VALID pawn move towards Goal {player_goal_row_idx+1} (Fwd>Side>Back). -> **STOP HERE.**

3.  **FIND BEST VALID PAWN MOVE:** Identify your best VALID pawn move (`BestPawnMove`: Fwd/Jump > Sideways). Does it exist?

4.  **CONSIDER WALL PLACEMENT? ({p_walls} walls left):**
    *   **STEP A: >> ABSOLUTE SELF-BLOCK CHECK << !!!** Before ANY wall placement, ask: "Does this wall drastically worsen MY path ({p_pos} to R{player_goal_row_idx+1})?" If YES, **DO NOT PLACE THAT WALL.** Consider a different wall or proceed to pawn moves.
    *   **STEP B: DEFENSIVE TRIGGER? ({defense_trigger}):** (Only proceed if potential walls pass Step A) Is Trigger TRUE (Opponent {o_dist} closer than you {p_dist}, advanced, walls left)? If YES: Find BEST VALID defensive wall (hindering {o_pos}, passed Step A). If found -> **Choose Defensive Wall.** -> **STOP.** Else (no good safe defensive wall) -> Go to Step 5.
    *   **STEP C: STRATEGIC WALL?** (Only if Trigger FALSE and Step A passed) Is `BestPawnMove` poor AND does a VALID wall offer HUGE gain (hurts opponent >> yours) AND pass Step A? If YES -> **Choose Strategic Wall.** -> **STOP.**
    *   **STEP D: NO GOOD WALL:** If no wall chosen yet -> Go to Step 5.

5.  **CHOOSE PAWN MOVE:** If you reached this step, **CHOOSE `BestPawnMove`** (from Step 3). If `BestPawnMove` didn't exist or was poor, choose the LEAST BAD valid pawn move (sideways > backward).

Your Task:
Player {player_id}: Analyze state. Follow DECISION FLOW strictly. Provide SINGLE VALID move. { "**CHOOSE BEST VALID MOVE FROM LISTS using RETRY STRATEGY.**" if is_retry_prompt else "" }

Output Format: (ONLY the move string)
- 'MOVE <Coord>' / 'WALL H <Coord>' / 'WALL V <Coord>'

Current Game State:
- You(P{player_id}): {p_pos} (W:{p_walls}, G:R{player_goal_row_idx+1}, D:{p_dist}) Opp(P{opponent_id}): {o_pos} (W:{o_walls}, G:R{opponent_goal_row_idx+1}, D:{o_dist})
- Walls: {walls_str} | Turn: P{player_id} | DefTrig:{defense_trigger} | Endgame:{is_endgame}

Provide your valid next move:
"""
    return prompt

# --- Ollama API Interaction & Validation (Unchanged) ---
def get_llm_move(prompt):
    payload = { "model": MODEL_NAME, "prompt": prompt, "stream": False, "options": { "temperature": 1.0, "top_k": 64, "top_p": 0.95, "min_p": 0.0, } }
    headers = {'Content-Type': 'application/json'}; timeout_seconds = 120
    try:
        response = requests.post(OLLAMA_API_URL, headers=headers, json=payload, timeout=timeout_seconds)
        response.raise_for_status(); response_data = response.json(); raw_response = response_data.get("response", "").strip()
        print(f"\n>LLM Raw Response ({MODEL_NAME}):"); print(raw_response); print("---------------------------------------")
        if not raw_response: print("Warning: LLM empty response."); return None
        return raw_response
    except Exception as e: print(f"\nError during Ollama API call: {e}"); return None
def validate_move_format(move_string):
    if not move_string or not isinstance(move_string, str): return False
    mp = re.compile(r"^MOVE\s+([A-I])([1-9])$"); wp = re.compile(r"^WALL\s+(H|V)\s+([A-H])([1-8])$"); is_m = bool(mp.match(move_string) or wp.match(move_string))
    if not is_m: print(f"Warning: LLM response '{move_string}' format invalid.")
    return is_m
# --- Self-Test Block (Unchanged) ---
if __name__ == "__main__":
     print("Testing ollama_interface.py - Final Strategy Refinements")
     state_defense = { "board_size": 9, "p1_pos": "E7", "p2_pos": "E5", "p1_walls": 8, "p2_walls": 8, "placed_walls": [], "current_player": 2, "winner": None, "is_game_over": False }
     prompt1 = create_quoridor_prompt(state_defense); print("\nPrompt 1 (P2 Defend): Def Trigger=True")
     state_normal = { "board_size": 9, "p1_pos": "E4", "p2_pos": "E5", "p1_walls": 6, "p2_walls": 6, "placed_walls": [], "current_player": 1, "winner": None, "is_game_over": False }
     prompt2 = create_quoridor_prompt(state_normal); print("\nPrompt 2 (Equal): Def Trigger=False")
     state_endgame = { "board_size": 9, "p1_pos": "C5", "p2_pos": "F5", "p1_walls": 0, "p2_walls": 10, "placed_walls": ["WHA1","WHD1"], "current_player": 1, "winner": None, "is_game_over": False }
     prompt3 = create_quoridor_prompt(state_endgame); print("\nPrompt 3 (Endgame): Endgame=True")
     print("\nSelf-testing complete.")