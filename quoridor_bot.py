# quoridor_bot.py (Refactored for performance and readability)

import math
import random
import time

try:
    # Import the game logic class and constants
    from quoridor_logic import QuoridorGame, BOARD_SIZE, R_OK
except ImportError as e:
    print(f"Error importing QuoridorGame: {e}")
    import sys
    sys.exit(1)


class QuoridorBot:
    """
    An AI agent for playing Quoridor using Minimax with Alpha-Beta Pruning.
    This version is optimized to avoid deep copying game states by using
    an undo_move method on the game object.
    """
    def __init__(self, player_id, search_depth=3):
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
        self.transposition_table = {} # Optimization: Not yet implemented
        self.nodes_visited = 0
        print(f"Initialized AlgoBot for P{self.player_id} | Depth={self.search_depth}")

    def evaluate_state(self, game_state: QuoridorGame):
        """
        Evaluates the game state from the perspective of this bot.
        Higher score is better for the bot.
        """
        winner = game_state.get_winner()
        if winner == self.player_id: return float('inf')
        if winner == self.opponent_id: return float('-inf')

        my_path_len = game_state.bfs_shortest_path_length(self.player_id)
        opp_path_len = game_state.bfs_shortest_path_length(self.opponent_id)

        if my_path_len == float('inf'): return float('-inf')
        if opp_path_len == float('inf'): return float('inf')

        # Core evaluation: Difference in shortest path to goal
        score = float(opp_path_len - my_path_len)

        # Wall Advantage: A small bonus for having more walls left
        wall_weight = 0.1
        my_walls = game_state.get_walls_left(self.player_id)
        opp_walls = game_state.get_walls_left(self.opponent_id)
        score += float((my_walls - opp_walls) * wall_weight)

        # Goal Proximity Bonus: A bonus for being closer to the goal
        # This incentivizes progress, especially when path difference is small.
        PROXIMITY_BONUS_FACTOR = 50
        if my_path_len > 0:
            score += PROXIMITY_BONUS_FACTOR / my_path_len

        return score

    def _get_ordered_moves(self, game_state: QuoridorGame, player_id: int):
        """ Generates and heuristically orders valid moves to improve alpha-beta pruning. """
        pawn_moves_with_scores = []
        current_pos = game_state.get_pawn_position(player_id)
        goal_row = BOARD_SIZE - 1 if player_id == 1 else 0

        if current_pos:
            valid_pawn_tuples = game_state.get_valid_pawn_moves(player_id)
            for pos in valid_pawn_tuples:
                coord_str = game_state._pos_to_coord(pos)
                if not coord_str: continue

                # Prioritize moves that advance towards the goal
                dist_change = abs(pos[0] - goal_row) - abs(current_pos[0] - goal_row)
                pawn_moves_with_scores.append((dist_change, f"MOVE {coord_str}"))

            # Sort pawn moves: advancing > sideways > retreating
            pawn_moves_with_scores.sort(key=lambda x: x[0])
            ordered_pawn_moves = [move for _, move in pawn_moves_with_scores]
        else:
            ordered_pawn_moves = []

        # Wall placements are generally considered after pawn moves
        valid_walls = game_state.get_valid_wall_placements(player_id)
        return ordered_pawn_moves + valid_walls

    def _minimax_alpha_beta(self, game_state: QuoridorGame, depth: int, alpha: float, beta: float, is_maximizing_player: bool):
        """ Minimax algorithm with Alpha-Beta Pruning using make_move and undo_move. """
        self.nodes_visited += 1

        if depth == 0 or game_state.is_game_over():
            return self.evaluate_state(game_state)

        current_player_turn = game_state.get_current_player()
        possible_moves = self._get_ordered_moves(game_state, current_player_turn)

        if not possible_moves:
            # If a player has no moves, it's a loss for them.
            return float('-inf') if current_player_turn == self.player_id else float('inf')

        if is_maximizing_player:
            max_eval = float('-inf')
            for move in possible_moves:
                success, move_obj = game_state.make_move(move)
                if not success: continue

                eval_score = self._minimax_alpha_beta(game_state, depth - 1, alpha, beta, False)
                game_state.undo_move(move_obj) # Backtrack

                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break # Prune
            return max_eval
        else:  # Minimizing player
            min_eval = float('inf')
            for move in possible_moves:
                success, move_obj = game_state.make_move(move)
                if not success: continue

                eval_score = self._minimax_alpha_beta(game_state, depth - 1, alpha, beta, True)
                game_state.undo_move(move_obj) # Backtrack

                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break # Prune
            return min_eval

    def find_best_move(self, game_state: QuoridorGame):
        """ Finds the best move for the bot using the Minimax search. """
        start_time = time.time()
        self.nodes_visited = 0

        if game_state.get_current_player() != self.player_id:
            print(f"Error: find_best_move called when not P{self.player_id}'s turn.")
            return None

        possible_moves = self._get_ordered_moves(game_state, self.player_id)
        if not possible_moves:
            print(f"Bot P{self.player_id}: No valid moves found!")
            return None

        best_move = possible_moves[0]
        max_eval = float('-inf')
        alpha = float('-inf')
        beta = float('inf')

        print(f"Bot P{self.player_id}: Finding best move (Depth={self.search_depth})...")

        for move in possible_moves:
            success, move_obj = game_state.make_move(move)
            if not success:
                print(f"  Skipping invalid simulation for move '{move}' at root.")
                continue

            # In the root call, the next turn is the opponent's (minimizing player)
            eval_score = self._minimax_alpha_beta(game_state, self.search_depth - 1, alpha, beta, False)
            game_state.undo_move(move_obj) # Undo the move after simulation

            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move

            alpha = max(alpha, eval_score)

        end_time = time.time()
        print(f"Bot P{self.player_id}: Best move: {best_move} | Score: {max_eval:.2f} | Nodes: {self.nodes_visited} | Time: {end_time - start_time:.3f}s")
        return best_move

# (Self-tests moved to tests/test_game.py)