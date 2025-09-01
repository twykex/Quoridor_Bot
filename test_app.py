import unittest
import json
from app import app, GameManager, HUMAN_PLAYER_ID, BOT_PLAYER_ID
from quoridor_logic import QuoridorGame

class TestQuoridorApp(unittest.TestCase):

    def setUp(self):
        """Set up a new test client before each test."""
        app.testing = True
        self.client = app.test_client()
        # It's useful to have direct access to a fresh game manager for some tests
        self.game_manager = GameManager()
        # Monkeypatch the app's game_manager with our test instance
        app.game_manager = self.game_manager

    def test_logic_pawn_move(self):
        """Test basic valid pawn movement in the logic class."""
        game = QuoridorGame()
        self.assertEqual(game.current_player, 1)
        success, reason = game.make_move("MOVE E2")
        self.assertTrue(success)
        self.assertEqual(reason, "OK")
        self.assertEqual(game.get_pawn_position(1), (1, 4)) # P1 is at E2
        self.assertEqual(game.current_player, 2)

    def test_logic_invalid_pawn_move(self):
        """Test basic invalid pawn movement."""
        game = QuoridorGame()
        success, reason = game.make_move("MOVE E3") # Invalid first move
        self.assertFalse(success)
        self.assertNotEqual(reason, "OK")

    def test_logic_win_condition(self):
        """Test the win condition logic."""
        game = QuoridorGame()
        game.pawn_positions[1] = (8, 4) # Manually set P1 to winning row
        game.current_player = 1
        game._check_win_condition()
        self.assertEqual(game.winner, 1)
        self.assertTrue(game.is_game_over())

    def test_logic_wall_placement_and_block(self):
        """Test valid wall placement and blocking."""
        game = QuoridorGame()
        game.make_move("MOVE E2") # P1 moves
        game.make_move("MOVE E8") # P2 moves
        # P1 places a wall to block P2's advance
        success, reason = game.make_move("WALL H E7")
        self.assertTrue(success)
        self.assertEqual(game.walls_left[1], 9)
        # P2 tries to move from E8 to E7, which is now blocked
        success, reason = game.make_move("MOVE E7")
        self.assertFalse(success)
        self.assertEqual(reason, "PawnMoveBlockedByWall")

    def test_bot_evaluation(self):
        """Test the bot's evaluation function with a clear advantage."""
        game = QuoridorGame()
        # P1 is one step from winning, P2 is far away
        game.pawn_positions = {1: (7, 4), 2: (1, 4)}
        game.walls_left = {1: 10, 2: 10}
        # Bot is P1, so perspective is P1
        score = self.game_manager.bot.evaluate_state(game, BOT_PLAYER_ID)
        # Expect a high score. The exact value depends on the heuristic.
        # path_diff = 1 - 1 = 0. wall_diff = 0. prox_bonus = 50 / 1 = 50. Total = 50.
        self.assertGreaterEqual(score, 50)

    def test_app_start_game(self):
        """Test the /start_game endpoint."""
        response = self.client.post('/start_game')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('game_state', data)
        self.assertTrue(data['game_state']['game_active'])

    def test_app_make_valid_human_move(self):
        """Test making a valid human move via the API."""
        self.client.post('/start_game') # Start a game
        # It's P2's (human) turn after the bot's initial move
        self.game_manager.game.current_player = HUMAN_PLAYER_ID

        response = self.client.post('/make_human_move', json={'move': 'MOVE E8'})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        # The bot will have made a move in response, so P1 is at a new spot
        self.assertNotEqual(data['game_state']['p1_pos'], 'E1')
        self.assertEqual(data['game_state']['p2_pos'], 'E8')

    def test_app_make_invalid_human_move(self):
        """Test making an invalid human move via the API."""
        self.client.post('/start_game')
        self.game_manager.game.current_player = HUMAN_PLAYER_ID

        response = self.client.post('/make_human_move', json={'move': 'MOVE E7'}) # Invalid move
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('PawnMoveNotAdjacent', data['reason'])

    def test_app_get_valid_moves_in_state(self):
        """Test that the valid_moves key is present for the human player."""
        self.client.post('/start_game')
        self.game_manager.game.current_player = HUMAN_PLAYER_ID # Force human's turn

        response = self.client.get('/game_state')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertIn('valid_moves', data)
        self.assertIn('pawn', data['valid_moves'])
        self.assertIn('wall', data['valid_moves'])
        # A few initial valid moves for P2 at E9 should be E8, D9, F9
        self.assertIn('E8', data['valid_moves']['pawn'])
        self.assertIn('D9', data['valid_moves']['pawn'])
        self.assertIn('F9', data['valid_moves']['pawn'])
        self.assertTrue(len(data['valid_moves']['wall']) > 0)

if __name__ == '__main__':
    unittest.main()
