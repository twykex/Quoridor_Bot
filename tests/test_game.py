import unittest
import sys
import os

# Add the root directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from quoridor_logic import QuoridorGame, R_OK, R_PAWN_OFFBOARD, R_WALL_OFFBOARD, R_WALL_OVERLAP, R_WALL_PATHBLOCK
from quoridor_bot import QuoridorBot

class TestQuoridorLogic(unittest.TestCase):

    def setUp(self):
        """Set up a new game instance for each test."""
        self.game = QuoridorGame()

    def test_initial_state(self):
        """Test the initial state of the game."""
        self.assertEqual(self.game.current_player, 1)
        self.assertEqual(self.game.get_pawn_coord(1), "E1")
        self.assertEqual(self.game.get_pawn_coord(2), "E9")
        self.assertEqual(self.game.get_walls_left(1), 10)
        self.assertEqual(self.game.get_walls_left(2), 10)
        self.assertIsNone(self.game.winner)

    def test_basic_pawn_moves(self):
        """Test basic valid and invalid pawn moves."""
        # P1 valid move
        success, result = self.game.make_move("MOVE E2")
        self.assertTrue(success)
        self.assertIsInstance(result, dict) # Should be a move object
        self.assertEqual(self.game.get_pawn_coord(1), "E2")
        self.assertEqual(self.game.current_player, 2)

        # P2 invalid move (not their turn)
        success, reason = self.game.make_move("MOVE E3")
        self.assertFalse(success)
        self.assertEqual(self.game.current_player, 2) # Player should not change

        # P2 valid move
        success, result = self.game.make_move("MOVE E8")
        self.assertTrue(success)
        self.assertIsInstance(result, dict)
        self.assertEqual(self.game.get_pawn_coord(2), "E8")
        self.assertEqual(self.game.current_player, 1)

    def test_get_valid_pawn_moves(self):
        """Test the get_valid_pawn_moves method."""
        self.game.make_move("MOVE E2")
        self.game.make_move("MOVE E8")
        # P1 is at E2, P2 is at E8
        valid_moves_p1 = self.game.get_valid_pawn_moves(1)
        # from E2 (1,4), can go to (0,4)D2, (2,4)F2, (1,3)E1, (1,5)E3
        # E1 is not valid as it is starting position of P1
        # E1 is (0,4), E2 is (1,4)
        # valid moves are (0,4)E1, (2,4)E3, (1,3)D2, (1,5)F2
        # let's check again
        # P1 starts at (0,4)E1. MOVE E2 -> (1,4)
        # P2 starts at (8,4)E9. MOVE E8 -> (7,4)
        # P1 at (1,4). Valid moves are (0,4)E1, (2,4)E3, (1,3)D2, (1,5)F2
        # The self-test in quoridor_logic.py has a bug.
        # It says valid moves from E2 are ['D2', 'E1', 'E3', 'F2']
        # Let's check the code:
        # r1,c1=sp; opp_r,opp_c=op;
        # for dr,dc in [(0,1),(0,-1),(1,0),(-1,0)]:
        # oh, it's (row, col), so (0,1) is right, not up.
        # (1,4) + (0,1) = (1,5) which is F2
        # (1,4) + (0,-1) = (1,3) which is D2
        # (1,4) + (1,0) = (2,4) which is E3
        # (1,4) + (-1,0) = (0,4) which is E1
        # So the valid moves are E1, E3, D2, F2
        # The self test is correct.
        self.assertEqual(len(valid_moves_p1), 4)
        self.assertIn((0, 4), valid_moves_p1) # E1
        self.assertIn((2, 4), valid_moves_p1) # E3
        self.assertIn((1, 3), valid_moves_p1) # D2
        self.assertIn((1, 5), valid_moves_p1) # F2


    def test_bfs_shortest_path(self):
        """Test the bfs_shortest_path_length method."""
        self.assertEqual(self.game.bfs_shortest_path_length(1), 8)
        self.assertEqual(self.game.bfs_shortest_path_length(2), 8)
        self.game.make_move("MOVE E2")
        self.game.make_move("MOVE E8")
        self.assertEqual(self.game.bfs_shortest_path_length(1), 7)
        self.assertEqual(self.game.bfs_shortest_path_length(2), 7)
        # Place a wall and check path length change
        self.game.placed_walls.add(('H', 1, 4)) # Wall at E2 H
        self.assertEqual(self.game.bfs_shortest_path_length(1), 8)


    def test_wall_placement(self):
        """Test valid and invalid wall placements."""
        self.game.make_move("MOVE E2") # P1
        self.game.make_move("MOVE E8") # P2
        # P1's turn
        success, result = self.game.make_move("WALL H E5")
        self.assertTrue(success)
        self.assertIsInstance(result, dict)
        self.assertEqual(self.game.get_walls_left(1), 9)
        self.assertEqual(self.game.current_player, 2)

        # Invalid: Overlapping wall
        success, reason = self.game.make_move("WALL H E5")
        self.assertFalse(success)
        self.assertEqual(reason, R_WALL_OVERLAP)
        self.assertEqual(self.game.get_walls_left(2), 10) # No change

    def test_undo_move(self):
        """Test the undo_move functionality."""
        # Get initial state
        initial_state = self.game.get_state_dict()

        # Make a pawn move and undo it
        success, move_obj_pawn = self.game.make_move("MOVE E2")
        self.assertTrue(success)
        self.game.undo_move(move_obj_pawn)
        self.assertEqual(self.game.get_state_dict(), initial_state)

        # Make a wall move and undo it
        self.game.current_player = 1 # Reset player for the next move
        success, move_obj_wall = self.game.make_move("WALL H E4")
        self.assertTrue(success)
        self.game.undo_move(move_obj_wall)
        self.assertEqual(self.game.get_state_dict(), initial_state)


class TestQuoridorBot(unittest.TestCase):

    def setUp(self):
        """Set up a new game and bot instance for each test."""
        self.game = QuoridorGame()
        self.bot1 = QuoridorBot(player_id=1, search_depth=2)
        self.bot2 = QuoridorBot(player_id=2, search_depth=2)

    def test_evaluate_state(self):
        """Test the bot's evaluation function."""
        # Initial state should be neutral
        score1 = self.bot1.evaluate_state(self.game)
        score2 = self.bot2.evaluate_state(self.game)
        self.assertAlmostEqual(score1, score2, delta=0.1)

        # After one move each
        self.game.make_move("MOVE E2")
        self.game.make_move("MOVE E8")
        score1_r1 = self.bot1.evaluate_state(self.game)
        score2_r1 = self.bot2.evaluate_state(self.game)
        self.assertAlmostEqual(score1_r1, score2_r1, delta=0.1)

        # Test wall evaluation
        game_with_wall = QuoridorGame()
        game_with_wall.pawn_positions[1] = (1, 4) # P1@E2
        game_with_wall.pawn_positions[2] = (7, 4) # P2@E8
        game_with_wall.placed_walls.add(('H', 1, 4)) # Wall at E2
        score1_wall = self.bot1.evaluate_state(game_with_wall)
        score2_wall = self.bot2.evaluate_state(game_with_wall)
        # The wall affects both players' shortest paths equally in this scenario.
        # P1's path length becomes 8, and P2's path length also becomes 8.
        # Therefore, their scores should be equal.
        self.assertAlmostEqual(score1_wall, score2_wall, delta=0.01)

        # Test trapped evaluation
        game_trap = QuoridorGame()
        walls_to_add = [('H',0,3),('H',0,4),('V',0,2),('V',1,2),('V',0,5),('V',1,5),('H',1,3),('H',1,4)]
        for w in walls_to_add:
            game_trap.placed_walls.add(w)
        trap_score1 = self.bot1.evaluate_state(game_trap)
        self.assertEqual(trap_score1, float('-inf'))

    def test_find_best_move(self):
        """Test the bot's move finding ability."""
        # In the initial state, the best move should be a forward pawn move.
        move1 = self.bot1.find_best_move(self.game)
        self.assertEqual(move1, "MOVE E2")

        # After P1 moves to E2, it's P2's turn. Best move should be MOVE E8.
        self.game.make_move(move1)
        move2 = self.bot2.find_best_move(self.game)
        self.assertEqual(move2, "MOVE E8")


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
