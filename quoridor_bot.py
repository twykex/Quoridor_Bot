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
    An AI agent for playing Quoridor. For 4-player games, it uses a simplified evaluation.
    """
    def __init__(self, player_id, search_depth=3, num_players=4):
        """
        Initializes the bot.
        Args:
            player_id (int): The ID of the player this bot represents.
            search_depth (int): How many half-turns (plies) ahead the bot should look.
            num_players (int): The number of players in the game.
        """
        self.player_id = player_id
        self.num_players = num_players
        # In a 4-player game, there isn't a single "opponent"
        self.opponent_ids = [p for p in range(1, num_players + 1) if p != player_id]
        self.search_depth = max(1, search_depth)
        self.transposition_table = {}
        self.nodes_visited = 0
        print(f"Initialized AlgoBot for P{self.player_id} | Depth={self.search_depth} | Players={self.num_players}")

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
        Higher score is better for that player.
        """
        winner = game_state.get_winner()
        if winner == perspective_player_id:
            return float('inf')
        if winner is not None: # Another player won
            return float('-inf')

        my_path_len = game_state.bfs_shortest_path_length(perspective_player_id)
        if my_path_len == float('inf'):
            return float('-inf')

        # In 4-player, a simple heuristic is to focus on your own progress.
        if self.num_players == 4:
            score = -my_path_len
            wall_weight = 0.1
            my_walls = game_state.get_walls_left(perspective_player_id)
            score += my_walls * wall_weight
            return score

        # Original 2-player evaluation
        opp_path_len = game_state.bfs_shortest_path_length(self.opponent_ids[0])
        if opp_path_len == float('inf'):
            return float('inf')

        score = float(opp_path_len - my_path_len)
        wall_weight = 0.1
        my_walls = game_state.get_walls_left(perspective_player_id)
        opp_walls = game_state.get_walls_left(self.opponent_ids[0])
        score += float((my_walls - opp_walls) * wall_weight)
        K_PROXIMITY = 50
        if my_path_len > 0:
            score += K_PROXIMITY / my_path_len
        return score

    def _get_ordered_moves(self, game_state: QuoridorGame, player_id: int):
        """ Generates and orders valid moves heuristically. """
        valid_pawn_tuples = game_state.get_valid_pawn_moves(player_id)
        pawn_moves_with_scores = []
        current_pos = game_state.get_pawn_position(player_id)

        if current_pos:
            for pos in valid_pawn_tuples:
                temp_game = copy.deepcopy(game_state)
                temp_game.pawn_positions[player_id] = pos
                score = -temp_game.bfs_shortest_path_length(player_id) # Negative path length
                pawn_moves_with_scores.append((score, f"MOVE {game_state._pos_to_coord(pos)}"))
            pawn_moves_with_scores.sort(key=lambda x: x[0], reverse=True)
            ordered_pawn_moves = [move for _, move in pawn_moves_with_scores]
        else:
            ordered_pawn_moves = []

        valid_walls = game_state.get_valid_wall_placements(player_id)
        return ordered_pawn_moves + valid_walls # Pawn moves first, then walls

    def minimax_alpha_beta(self, game_state: QuoridorGame, depth: int, alpha: float, beta: float, maximizing_player: bool):
        """ Minimax for multi-player games (simplified). """
        self.nodes_visited += 1
        state_key = self._get_state_key(game_state)
        if state_key in self.transposition_table:
            return self.transposition_table[state_key]

        if depth == 0 or game_state.is_game_over():
            score = self.evaluate_state(game_state, self.player_id)
            self.transposition_table[state_key] = score
            return score

        current_player_turn = game_state.current_player
        possible_moves = self._get_ordered_moves(game_state, current_player_turn)

        if not possible_moves:
            return self.evaluate_state(game_state, self.player_id)

        if current_player_turn == self.player_id: # Maximizing player
            max_eval = float('-inf')
            for move in possible_moves:
                child_state = copy.deepcopy(game_state)
                child_state.make_move(move)
                eval_score = self.minimax_alpha_beta(child_state, depth - 1, alpha, beta, False)
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            self.transposition_table[state_key] = max_eval
            return max_eval
        else: # Opponent's turn (minimizing for us)
            min_eval = float('inf')
            for move in possible_moves:
                child_state = copy.deepcopy(game_state)
                child_state.make_move(move)
                eval_score = self.minimax_alpha_beta(child_state, depth - 1, alpha, beta, True)
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
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
    print("--- Testing QuoridorBot with 4 players ---")
    test_depth = 1 # Use depth 1 for faster tests
    bots = {i: QuoridorBot(player_id=i, search_depth=test_depth, num_players=4) for i in range(1, 5)}
    test_game = QuoridorGame(num_players=4)

    print("\n--- Initial State Evaluation ---")
    for i in range(1, 5):
        score = bots[i].evaluate_state(test_game, i)
        print(f"Initial Eval for P{i}: Score = {score:.2f}")

    print("\n--- Bot 1 Finding First Move ---")
    move1 = bots[1].find_best_move(test_game)
    print(f"Bot 1 suggests: {move1}")
    if move1:
        test_game.make_move(move1)

    print(f"\n--- State after P1 move ---")
    print(f"Current player: {test_game.current_player}")
    print(f"Pawn positions: {test_game.get_state_dict()['pawn_positions']}")

    print("\n--- Bot 2 Finding First Move ---")
    move2 = bots[2].find_best_move(test_game)
    print(f"Bot 2 suggests: {move2}")
    if move2:
        test_game.make_move(move2)

    print(f"\n--- State after P2 move ---")
    print(f"Current player: {test_game.current_player}")
    print(f"Pawn positions: {test_game.get_state_dict()['pawn_positions']}")