# quoridor_bot.py (Algorithmic Bot - Goal Proximity Bonus Added)

import math
import random
import time
import copy # Needed for deep copying game states during search

try:
    # Import the game logic class and constants
    from quoridor_logic import QuoridorGame, BOARD_SIZE, R_OK, INITIAL_WALLS
except ImportError as e:
    print(f"Error importing QuoridorGame: {e}")
    import sys
    sys.exit(1)


class QuoridorBot:
    """
    An AI agent for playing Quoridor using Minimax with Alpha-Beta Pruning.
    Includes a goal proximity bonus in evaluation.
    """
    def __init__(self, player_id, search_depth=3): # Default depth 3
        """
        Initializes the bot.
        Args:
            player_id (int): The ID of the player this bot represents (1 or 2).
            search_depth (int): How many half-turns (plies) ahead the bot should look.
        """
        if player_id not in [1, 2]:
            raise ValueError("Player ID must be 1 or 2")
        self.player_id = player_id
        self.opponent_id = 3 - player_id
        self.search_depth = max(1, search_depth)
        self.transposition_table = {}
        self.nodes_visited = 0
        print(f"Initialized AlgoBot for P{self.player_id} | Depth={self.search_depth}")

    def _get_state_key(self, game_state: QuoridorGame):
        """
        Creates a hashable key representing the current game state.
        """
        return (
            frozenset(game_state.pawn_positions.items()),
            frozenset(game_state.placed_walls),
            frozenset(game_state.walls_left.items()),
            game_state.current_player
        )

    def evaluate_state(self, game_state: QuoridorGame, perspective_player_id: int):
        """
        Evaluates the game state from the perspective of 'perspective_player_id'.
        Higher score is better for that player. Includes goal proximity bonus.
        """
        winner = game_state.get_winner()
        my_id = perspective_player_id
        opp_id = 3 - my_id

        if winner == my_id: return float('inf')
        if winner == opp_id: return float('-inf')

        my_path_len = game_state.bfs_shortest_path_length(my_id)
        opp_path_len = game_state.bfs_shortest_path_length(opp_id)

        if my_path_len == float('inf'): return float('-inf') # Cannot win
        if opp_path_len == float('inf'): return float('inf')  # Opponent cannot win

        # Core evaluation: Path difference
        score = float(opp_path_len - my_path_len)

        # Wall Advantage
        wall_weight = 0.1
        my_walls = game_state.get_walls_left(my_id)
        opp_walls = game_state.get_walls_left(opp_id)
        score += float((my_walls - opp_walls) * wall_weight)

        # --- Goal Proximity Bonus ---
        K_PROXIMITY = 50 # Bonus factor - Tune this value if needed
        if my_path_len > 0:
             # Add bonus inversely proportional to *my* distance
             score += K_PROXIMITY / my_path_len
        # Optional: Subtract bonus based on opponent's distance?
        # if opp_path_len > 0:
        #     score -= (K_PROXIMITY / opp_path_len) * 0.5 # Smaller penalty for opponent being close

        return score

    def _get_ordered_moves(self, game_state: QuoridorGame, player_id: int):
        """ Generates and orders valid moves heuristically. """
        # --- Pawn Move Ordering ---
        valid_pawn_tuples = game_state.get_valid_pawn_moves(player_id)
        pawn_moves = []
        current_pos = game_state.get_pawn_position(player_id)
        goal_row = BOARD_SIZE - 1 if player_id == 1 else 0

        if current_pos:
            for pos in valid_pawn_tuples:
                coord_str = game_state._pos_to_coord(pos)
                if not coord_str: continue
                move_str = f"MOVE {coord_str}"
                # Prioritize moves that advance towards the goal
                dist_change = abs(pos[0] - goal_row) - abs(current_pos[0] - goal_row)
                pawn_moves.append((dist_change, move_str))
            pawn_moves.sort(key=lambda x: x[0]) # Sort by smallest (most negative) distance change
            ordered_pawn_moves = [move for _, move in pawn_moves]
        else:
            ordered_pawn_moves = []

        # --- Wall Move Ordering (with impact analysis) ---
        if game_state.get_walls_left(player_id) > 0:
            wall_moves_with_scores = []
            valid_walls = game_state.get_valid_wall_placements(player_id)
            # Get path lengths *before* any new wall
            my_path_before = game_state.bfs_shortest_path_length(self.player_id)
            opp_path_before = game_state.bfs_shortest_path_length(self.opponent_id)

            for wall_move in valid_walls:
                temp_game = copy.deepcopy(game_state)
                success, _ = temp_game.make_move(wall_move)
                if not success: continue

                # Get path lengths *after* the wall is placed
                my_path_after = temp_game.bfs_shortest_path_length(self.player_id)
                opp_path_after = temp_game.bfs_shortest_path_length(self.opponent_id)

                # Calculate the impact
                my_path_increase = my_path_after - my_path_before
                opp_path_increase = opp_path_after - opp_path_before

                # We want to maximize the opponent's path increase while minimizing ours
                # A higher score is a better wall placement
                wall_score = opp_path_increase - my_path_increase
                wall_moves_with_scores.append((wall_score, wall_move))

            # Sort walls from most impactful to least impactful
            wall_moves_with_scores.sort(key=lambda x: x[0], reverse=True)
            ordered_wall_moves = [move for _, move in wall_moves_with_scores]
        else:
            ordered_wall_moves = []

        # Combine pawn moves and wall moves, pawn moves are generally preferred first
        return ordered_pawn_moves + ordered_wall_moves


    def minimax_alpha_beta(self, game_state: QuoridorGame, depth: int, alpha: float, beta: float, maximizing_player: bool):
        """ Minimax algorithm with Alpha-Beta Pruning. """
        self.nodes_visited += 1
        state_key = self._get_state_key(game_state)
        if state_key in self.transposition_table:
            return self.transposition_table[state_key]

        if depth == 0 or game_state.is_game_over():
            # Evaluate always from the perspective of the bot running the search
            score = self.evaluate_state(game_state, self.player_id)
            self.transposition_table[state_key] = score
            return score

        current_player_turn = game_state.current_player
        possible_moves = self._get_ordered_moves(game_state, current_player_turn)

        if not possible_moves:
             return float('-inf') if current_player_turn == self.player_id else float('inf')

        if maximizing_player:
            max_eval = float('-inf')
            for move in possible_moves:
                try:
                    child_state = copy.deepcopy(game_state)
                    success, _ = child_state.make_move(move)
                    if not success: continue
                    eval_score = self.minimax_alpha_beta(child_state, depth - 1, alpha, beta, False)
                    max_eval = max(max_eval, eval_score)
                    alpha = max(alpha, eval_score)
                    if beta <= alpha: break
                except Exception as e: print(f"!! Err MAX sim move {move}: {e}"); continue
            self.transposition_table[state_key] = max_eval
            return max_eval
        else: # Minimizing player
            min_eval = float('inf')
            for move in possible_moves:
                try:
                    child_state = copy.deepcopy(game_state)
                    success, _ = child_state.make_move(move)
                    if not success: continue
                    eval_score = self.minimax_alpha_beta(child_state, depth - 1, alpha, beta, True)
                    min_eval = min(min_eval, eval_score)
                    beta = min(beta, eval_score)
                    if beta <= alpha: break
                except Exception as e: print(f"!! Err MIN sim move {move}: {e}"); continue
            self.transposition_table[state_key] = min_eval
            return min_eval


    def find_best_move(self, game_state: QuoridorGame):
        """ Finds the best move using Minimax with Alpha-Beta Pruning. """
        start_time = time.time(); self.nodes_visited = 0
        print(f"Bot P{self.player_id}: Finding best move (Depth={self.search_depth})...")

        if game_state.current_player != self.player_id:
            print(f"Error: find_best_move called when not P{self.player_id}'s turn."); return None

        possible_moves = self._get_ordered_moves(game_state, self.player_id)
        if not possible_moves: print(f"Bot P{self.player_id}: No valid moves!"); return None

        best_move = possible_moves[0]; max_eval = float('-inf')
        alpha = float('-inf'); beta = float('inf')

        for move in possible_moves:
            try:
                # print(f"  Testing move: {move}") # Debug
                child_state = copy.deepcopy(game_state)
                success, _ = child_state.make_move(move)
                if not success: print(f"  Skipping invalid sim for {move} at root."); continue

                eval_score = self.minimax_alpha_beta(child_state, self.search_depth - 1, alpha, beta, False)
                # print(f"  Move: {move} -> Score: {eval_score:.2f}") # Debug

                if eval_score > max_eval:
                    max_eval = eval_score
                    best_move = move
                alpha = max(alpha, eval_score)

            except Exception as e: print(f"!! Error ROOT sim move {move}: {e}"); continue

        end_time = time.time()
        print(f"Bot P{self.player_id}: Best move: {best_move} | Score: {max_eval:.2f} | Nodes: {self.nodes_visited} | Time: {end_time - start_time:.3f}s")
        return best_move

# --- Example Usage / Self-Tests ---
if __name__ == "__main__":
    print("--- Testing QuoridorBot with Minimax (Goal Proximity Bonus) ---")
    # Use Depth 2 for faster self-test runs
    test_depth = 2
    bot1 = QuoridorBot(player_id=1, search_depth=test_depth)
    bot2 = QuoridorBot(player_id=2, search_depth=test_depth)
    test_game = QuoridorGame()


    print("\n--- Initial State ---")
    score1 = bot1.evaluate_state(test_game, 1)
    score2 = bot2.evaluate_state(test_game, 2)
    print(f"Initial Eval: P1 Score = {score1:.2f}, P2 Score = {score2:.2f}") # Expect ~5.6, ~5.6

    print("\n--- Bot 1 Finding First Move ---")
    move1 = bot1.find_best_move(test_game)
    print(f"Bot 1 suggests: {move1}")
    if move1: res1, rea1 = test_game.make_move(move1)

    print("\n--- Bot 2 Finding First Move ---")
    if test_game.current_player == bot2.player_id:
        move2 = bot2.find_best_move(test_game)
        print(f"Bot 2 suggests: {move2}")
        if move2: res2, rea2 = test_game.make_move(move2)
    else: print("Error: Not Bot 2's turn.")

    print(f"\n--- State after 1 round ---")
    score1_r1 = bot1.evaluate_state(test_game, 1)
    score2_r1 = bot2.evaluate_state(test_game, 2)
    print(f"Current State Eval: P1 Score = {score1_r1:.2f}, P2 Score = {score2_r1:.2f}")
    print(f"Board: P1@{test_game.get_pawn_coord(1)} P2@{test_game.get_pawn_coord(2)}")

    print("\n--- Bot 1 Finding Second Move ---")
    if test_game.current_player == bot1.player_id:
        move3 = bot1.find_best_move(test_game)
        print(f"Bot 1 suggests: {move3}")
    else: print("Error: Not Bot 1's turn.")


    # --- Corrected Wall Evaluation Test (Using the bot's eval) ---
    print("\n--- Testing Evaluation with Wall ---")
    test_game_with_wall = QuoridorGame(); test_game_with_wall.pawn_positions[1] = (1, 4); test_game_with_wall.pawn_positions[2] = (7, 4); test_game_with_wall.placed_walls.add(('H', 1, 4)); test_game_with_wall.walls_left[1] = 9; print(f"State: P1@E2, P2@E8, Wall H E2")
    score1_wall = bot1.evaluate_state(test_game_with_wall, 1) # Eval for P1
    score2_wall = bot2.evaluate_state(test_game_with_wall, 2) # Eval for P2
    print(f"Eval with WALL H E2: P1 Score = {score1_wall:.2f}, P2 Score = {score2_wall:.2f}") # Expect P1 score < P2 score

    # --- Trapped Test ---
    print("\n--- Testing Trapped Evaluation ---")
    game_trap = QuoridorGame(); walls_to_add = [('H',0,3),('H',0,4),('V',0,2),('V',1,2),('V',0,5),('V',1,5),('H',1,3),('H',1,4)]; [game_trap.placed_walls.add(w) for w in walls_to_add]
    trap_score1 = bot1.evaluate_state(game_trap, 1)
    print(f"Trapped P1 evaluation = {trap_score1}") # Expect -inf