# llm_bot.py

import time
import os

try:
    from quoridor_logic import QuoridorGame
    from ollama_interface import create_quoridor_prompt, get_llm_move, validate_move_format
except ImportError as e:
    print(f"Error importing modules in llm_bot.py: {e}")
    import sys
    sys.exit(1)

class LLMBot:
    """
    A Quoridor bot that uses a Large Language Model (LLM) via the Ollama interface
    to decide on its moves.
    """
    def __init__(self, player_id, model_name="gemma:2b", max_retries=3):
        """
        Initializes the LLM bot.
        Args:
            player_id (int): The player ID for the bot (1 or 2).
            model_name (str): The name of the Ollama model to use.
            max_retries (int): The maximum number of times to retry on LLM failure.
        """
        if player_id not in [1, 2]:
            raise ValueError("Player ID must be 1 or 2")
        self.player_id = player_id
        self.opponent_id = 3 - player_id
        self.model_name = os.getenv("OLLAMA_MODEL", model_name)
        self.max_retries = max_retries
        print(f"Initialized LLMBot for P{self.player_id} | Model={self.model_name}")

    def find_best_move(self, game_state: QuoridorGame):
        """
        Finds the best move by querying the LLM, with a retry mechanism.
        """
        start_time = time.time()
        print(f"LLM Bot P{self.player_id}: Finding best move...")

        if game_state.get_current_player() != self.player_id:
            print(f"Error: find_best_move called when not P{self.player_id}'s turn.")
            return None

        fail_reason = None
        valid_pawn_moves = None
        valid_wall_placements = None

        for attempt in range(self.max_retries):
            print(f"  Attempt {attempt + 1}/{self.max_retries}...")

            prompt = create_quoridor_prompt(
                game_state.get_state_dict(),
                last_move_fail_reason=fail_reason,
                valid_pawn_moves_list=valid_pawn_moves,
                valid_wall_placements_list=valid_wall_placements
            )

            llm_response = get_llm_move(prompt, self.model_name)

            if not llm_response:
                fail_reason = "The LLM returned an empty response."
                continue

            is_valid_format, move_type, details = validate_move_format(llm_response)
            if not is_valid_format:
                fail_reason = f"The move '{llm_response}' has an invalid format."
                valid_pawn_coords = [game_state._pos_to_coord(p) for p in game_state.get_valid_pawn_moves(self.player_id)]
                valid_pawn_moves = sorted([p for p in valid_pawn_coords if p is not None])
                valid_wall_placements = game_state.get_valid_wall_placements(self.player_id)
                continue

            # Check logical validity without changing the game state
            is_logically_valid = False
            reason = "Unknown"
            if move_type == "MOVE":
                target_pos = game_state._coord_to_pos(details)
                if game_state.is_valid_pawn_move(self.player_id, target_pos):
                    is_logically_valid = True
                else:
                    # This part is tricky as is_valid_pawn_move doesn't give a reason
                    reason = "Pawn move is not allowed by game rules."
            elif move_type == "WALL":
                orientation, coord = details
                pos = game_state._coord_to_pos(coord)
                if pos:
                    is_valid, reason = game_state.check_wall_placement_validity(self.player_id, orientation, pos[0], pos[1])
                    if is_valid:
                        is_logically_valid = True

            if is_logically_valid:
                end_time = time.time()
                print(f"LLM Bot P{self.player_id}: Found valid move '{llm_response}' in {end_time - start_time:.3f}s")
                return llm_response
            else:
                fail_reason = f"The move '{llm_response}' was invalid. Reason: {reason}"
                valid_pawn_coords = [game_state._pos_to_coord(p) for p in game_state.get_valid_pawn_moves(self.player_id)]
                valid_pawn_moves = sorted([p for p in valid_pawn_coords if p is not None])
                valid_wall_placements = game_state.get_valid_wall_placements(self.player_id)

        print(f"LLM Bot P{self.player_id}: Failed to find a valid move after {self.max_retries} attempts.")
        # As a fallback, return the first valid pawn move if any exist
        fallback_moves = game_state.get_valid_pawn_moves(self.player_id)
        if fallback_moves:
            fallback_coord = game_state._pos_to_coord(list(fallback_moves)[0])
            fallback_move = f"MOVE {fallback_coord}"
            print(f"  Fallback: Choosing first valid pawn move: {fallback_move}")
            return fallback_move

        return None
