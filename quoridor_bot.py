# quoridor_bot.py (Refactored for Readability)

import math
import random
import time
import copy
import sys

try:
    from quoridor_logic import QuoridorGame, BOARD_SIZE, R_OK
except ImportError as e:
    print(f"Error importing QuoridorGame: {e}")
    sys.exit(1)


class QuoridorBot:
    """
    An AI agent for playing Quoridor using Minimax with Alpha-Beta Pruning.
    """
    def __init__(self, player_id, search_depth=3):
        """
        Initializes the bot.

        Args:
            player_id (int): The ID of the player this bot represents (1 or 2).
            search_depth (int): How many half-turns (plies) the bot should look ahead.
                                Higher values lead to stronger but slower play.
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
        Creates a unique, hashable key for the given game state.
        This is used for the transposition table.
        The key is a tuple of the pawn positions, placed walls, and current player.
        """
        p1_pos = game_state.get_pawn_position(1)
        p2_pos = game_state.get_pawn_position(2)
        # frozenset is used to make the set of walls hashable
        walls = frozenset(game_state.get_placed_walls())
        return (p1_pos, p2_pos, walls, game_state.current_player)

    def evaluate_state(self, game_state: QuoridorGame, perspective_player_id: int):
        """
        Evaluates the game state from the perspective of a given player.
        A higher score is better for that player.

        The evaluation function considers:
        1.  Win/Loss conditions (infinite scores).
        2.  The difference in the shortest path length to the goal.
        3.  The number of walls remaining for each player.
        4.  A bonus for being closer to the goal, to encourage progress.

        Args:
            game_state (QuoridorGame): The game state to evaluate.
            perspective_player_id (int): The player from whose perspective to evaluate.

        Returns:
            float: The evaluated score of the game state.
        """
        winner = game_state.get_winner()
        opponent_id = game_state.get_opponent(perspective_player_id)

        if winner == perspective_player_id:
            return float('inf')
        if winner == opponent_id:
            return float('-inf')

        my_path_len = game_state.bfs_shortest_path_length(perspective_player_id)
        opp_path_len = game_state.bfs_shortest_path_length(opponent_id)

        # If a player has no path, it's a losing position for them.
        if my_path_len == float('inf'):
            return float('-inf')
        if opp_path_len == float('inf'):
            return float('inf')

        # Core evaluation: The primary driver is having a shorter path than the opponent.
        path_difference = opp_path_len - my_path_len
        score = float(path_difference)

        # Wall Advantage: Having more walls is a slight advantage.
        wall_weight = 0.1
        my_walls = game_state.get_walls_left(perspective_player_id)
        opp_walls = game_state.get_walls_left(opponent_id)
        score += float((my_walls - opp_walls) * wall_weight)

        # Goal Proximity Bonus: Encourage the bot to make forward progress.
        # The bonus is inversely proportional to the path length.
        proximity_bonus_factor = 50
        if my_path_len > 0:
            score += proximity_bonus_factor / my_path_len

        return score

    def _get_ordered_moves(self, game_state: QuoridorGame, player_id: int):
        """
        Generates and heuristically orders valid moves to improve alpha-beta pruning.
        Pawn moves that advance towards the goal are prioritized.

        Args:
            game_state (QuoridorGame): The current game state.
            player_id (int): The player for whom to generate moves.

        Returns:
            list[str]: A list of move strings, ordered from best to worst guess.
        """
        # Get all valid pawn moves (as position tuples)
        valid_pawn_positions = game_state.get_valid_pawn_moves(player_id)
        pawn_moves_with_scores = []
        current_pos = game_state.get_pawn_position(player_id)
        goal_row = BOARD_SIZE - 1 if player_id == 1 else 0

        if current_pos:
            current_dist_to_goal = abs(current_pos[0] - goal_row)
            for pos in valid_pawn_positions:
                coord_str = game_state._pos_to_coord(pos)
                if not coord_str:
                    continue
                move_str = f"MOVE {coord_str}"
                # Score is the change in distance to the goal row (negative is better)
                new_dist_to_goal = abs(pos[0] - goal_row)
                score = new_dist_to_goal - current_dist_to_goal
                pawn_moves_with_scores.append((score, move_str))

            # Sort moves by score (ascending, so better moves are first)
            pawn_moves_with_scores.sort(key=lambda x: x[0])
            ordered_pawn_moves = [move for _, move in pawn_moves_with_scores]
        else:
            ordered_pawn_moves = []

        # Wall placements are considered after pawn moves.
        # A more advanced heuristic could score wall placements as well.
        valid_walls = game_state.get_valid_wall_placements(player_id)
        return ordered_pawn_moves + valid_walls

    def minimax_alpha_beta(self, game_state: QuoridorGame, depth: int, alpha: float, beta: float, is_maximizing_player: bool):
        """
        The core Minimax algorithm with Alpha-Beta Pruning.

        Args:
            game_state (QuoridorGame): The current state for this node of the search.
            depth (int): The remaining depth to search.
            alpha (float): The alpha value for pruning.
            beta (float): The beta value for pruning.
            is_maximizing_player (bool): True if this node is for the maximizing player, False otherwise.

        Returns:
            float: The evaluated score for this branch of the search tree.
        """
        self.nodes_visited += 1
        state_key = self._get_state_key(game_state)

        # Check transposition table
        if state_key in self.transposition_table and self.transposition_table[state_key]['depth'] >= depth:
            return self.transposition_table[state_key]['score']

        if depth == 0 or game_state.is_game_over():
            # Evaluation is always from the bot's own perspective.
            score = self.evaluate_state(game_state, self.player_id)
            self.transposition_table[state_key] = {'score': score, 'depth': depth}
            return score

        current_player_turn = game_state.current_player
        possible_moves = self._get_ordered_moves(game_state, current_player_turn)

        if not possible_moves:
            # If a player has no moves, they have lost.
            return float('-inf') if current_player_turn == self.player_id else float('inf')

        if is_maximizing_player:
            max_eval = float('-inf')
            for move in possible_moves:
                child_state = copy.deepcopy(game_state)
                success, _ = child_state.make_move(move)
                if not success:
                    continue
                eval_score = self.minimax_alpha_beta(child_state, depth - 1, alpha, beta, False)
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break  # Prune
            self.transposition_table[state_key] = {'score': max_eval, 'depth': depth}
            return max_eval
        else:  # Minimizing player
            min_eval = float('inf')
            for move in possible_moves:
                child_state = copy.deepcopy(game_state)
                success, _ = child_state.make_move(move)
                if not success:
                    continue
                eval_score = self.minimax_alpha_beta(child_state, depth - 1, alpha, beta, True)
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break  # Prune
            self.transposition_table[state_key] = {'score': min_eval, 'depth': depth}
            return min_eval

    def find_best_move(self, game_state: QuoridorGame):
        """
        Finds the best move for the bot in the given game state.
        This is the entry point for the Minimax search.

        Args:
            game_state (QuoridorGame): The current state of the game.

        Returns:
            str or None: The best move string, or None if no move is found.
        """
        start_time = time.time()
        self.nodes_visited = 0
        self.transposition_table.clear()  # Clear table for new move calculation
        print(f"Bot P{self.player_id}: Finding best move (Depth={self.search_depth})...")

        if game_state.current_player != self.player_id:
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

        for move in possible_moves:
            # Create a deep copy for simulation at the root of the search
            child_state = copy.deepcopy(game_state)
            success, reason = child_state.make_move(move)
            if not success:
                # This should not happen if get_valid_moves is correct
                print(f"  Skipping invalid move '{move}' at root. Reason: {reason}")
                continue

            # The next level of minimax is for the minimizing player
            eval_score = self.minimax_alpha_beta(child_state, self.search_depth - 1, alpha, beta, False)

            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move

            alpha = max(alpha, eval_score)

        end_time = time.time()
        print(f"Bot P{self.player_id}: Best move: {best_move} | Score: {max_eval:.2f} | Nodes: {self.nodes_visited} | Time: {end_time - start_time:.3f}s")
        return best_move


# --- Example Usage / Self-Tests ---
def run_self_tests():
    """Runs a series of tests to validate the bot's functionality."""
    print("--- Testing QuoridorBot with Minimax ---")
    # Use Depth 2 for faster self-test runs
    test_depth = 2
    bot1 = QuoridorBot(player_id=1, search_depth=test_depth)
    bot2 = QuoridorBot(player_id=2, search_depth=test_depth)
    test_game = QuoridorGame()

    print("\n--- Initial State Evaluation ---")
    score1 = bot1.evaluate_state(test_game, 1)
    score2 = bot2.evaluate_state(test_game, 2)
    # Scores should be equal and based on proximity bonus
    print(f"Initial Eval: P1 Score = {score1:.2f}, P2 Score = {score2:.2f}")

    print("\n--- Bot 1 Finding First Move ---")
    move1 = bot1.find_best_move(test_game)
    print(f"Bot 1 suggests: {move1}")
    if move1:
        test_game.make_move(move1)

    print("\n--- Bot 2 Finding First Move ---")
    if test_game.current_player == bot2.player_id:
        move2 = bot2.find_best_move(test_game)
        print(f"Bot 2 suggests: {move2}")
        if move2:
            test_game.make_move(move2)
    else:
        print("Error: Not Bot 2's turn.")

    print(f"\n--- State after 1 round ---")
    score1_r1 = bot1.evaluate_state(test_game, 1)
    score2_r1 = bot2.evaluate_state(test_game, 2)
    print(f"Current State Eval: P1 Score = {score1_r1:.2f}, P2 Score = {score2_r1:.2f}")
    print(f"Board: P1@{test_game.get_pawn_coord(1)} P2@{test_game.get_pawn_coord(2)}")

    print("\n--- Testing Evaluation with Wall ---")
    game_with_wall = QuoridorGame()
    game_with_wall.pawn_positions[1] = (1, 4)  # P1 at E2
    game_with_wall.pawn_positions[2] = (7, 4)  # P2 at E8
    game_with_wall.placed_walls.add(('H', 1, 4))  # Wall at H E2
    game_with_wall.walls_left[1] = 9
    print(f"State: P1@E2, P2@E8, Wall H E2")
    score1_wall = bot1.evaluate_state(game_with_wall, 1)
    score2_wall = bot2.evaluate_state(game_with_wall, 2)
    # P1's path is now longer, so its score should be lower.
    print(f"Eval with WALL H E2: P1 Score = {score1_wall:.2f}, P2 Score = {score2_wall:.2f}")

    print("\n--- Testing Trapped Evaluation ---")
    game_trap = QuoridorGame()
    # Create a box of walls around player 1's starting area
    walls_to_add = [
        ('H', 0, 3), ('H', 0, 4), ('V', 0, 2), ('V', 1, 2),
        ('V', 0, 5), ('V', 1, 5), ('H', 1, 3), ('H', 1, 4)
    ]
    for wall in walls_to_add:
        game_trap.placed_walls.add(wall)
    trap_score1 = bot1.evaluate_state(game_trap, 1)
    print(f"Trapped P1 evaluation = {trap_score1}") # Expect -inf

if __name__ == "__main__":
    run_self_tests()