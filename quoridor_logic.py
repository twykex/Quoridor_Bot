# quoridor_logic.py (Refactored for Readability)

import collections
import sys
import math
import copy
import traceback

BOARD_SIZE = 9
INITIAL_WALLS = 10

# --- Result Codes ---
R_OK = "OK"
R_GAMEOVER = "GameOver"
R_INV_FORMAT = "InvalidMoveFormat"
R_INV_COORD = "InvalidCoordinate"
R_INV_ORIENT = "InvalidWallOrientation"
R_PAWN_OFFBOARD = "PawnMoveOffBoard"
R_PAWN_OCCUPIED = "PawnMoveToOccupiedSquare"
R_PAWN_WALLBLOCK = "PawnMoveBlockedByWall"
R_PAWN_NOTADJ = "PawnMoveNotAdjacentOrValidJump"
R_WALL_NOWALLS = "NoWallsLeft"
R_WALL_OFFBOARD = "WallPlacementOffBoard"
R_WALL_OVERLAP = "WallOverlapsExistingWall"
R_WALL_CONFLICT = "WallConflictsWithAdjacentWall"
R_WALL_PATHBLOCK = "WallBlocksLastPath"


class QuoridorGame:
    """
    Manages the state and rules of a Quoridor game.
    """
    def __init__(self):
        self.board_size = BOARD_SIZE
        self.walls_total = INITIAL_WALLS
        self.pawn_positions = {1: (0, 4), 2: (8, 4)}  # {player_id: (row, col)}
        self.walls_left = {1: self.walls_total, 2: self.walls_total}
        self.placed_walls = set()  # {(orientation, row, col)}
        self.current_player = 1
        self.winner = None
        self._move_history = []

    # --- Coordinate Helpers ---
    def _coord_to_pos(self, coord_str):
        if not isinstance(coord_str, str) or len(coord_str) < 2:
            return None
        col_char = coord_str[0].upper()
        row_str = coord_str[1:]
        if not ('A' <= col_char <= chr(ord('A') + self.board_size - 1)) or not row_str.isdigit():
            return None
        col = ord(col_char) - ord('A')
        row = int(row_str) - 1
        if not (0 <= row < self.board_size and 0 <= col < self.board_size):
            return None
        return row, col

    def _pos_to_coord(self, pos):
        if not isinstance(pos, tuple) or len(pos) != 2:
            return None
        row, col = pos
        if not (0 <= row < self.board_size and 0 <= col < self.board_size):
            return None
        return f"{chr(ord('A') + col)}{row + 1}"

    # --- Getters ---
    def get_state_dict(self):
        return {
            "board_size": self.board_size,
            "p1_pos": self._pos_to_coord(self.pawn_positions.get(1)),
            "p2_pos": self._pos_to_coord(self.pawn_positions.get(2)),
            "p1_walls": self.walls_left.get(1),
            "p2_walls": self.walls_left.get(2),
            "placed_walls": sorted(list(self.get_placed_wall_strings())),
            "current_player": self.current_player,
            "winner": self.winner,
            "is_game_over": self.is_game_over()
        }

    def get_pawn_position(self, player_id):
        return self.pawn_positions.get(player_id)

    def get_pawn_coord(self, player_id):
        return self._pos_to_coord(self.get_pawn_position(player_id))

    def get_walls_left(self, player_id):
        return self.walls_left.get(player_id, 0)

    def get_placed_walls(self):
        return self.placed_walls.copy()

    def get_placed_wall_strings(self):
        wall_strings = set()
        for orientation, row, col in self.placed_walls:
            coord = self._pos_to_coord((row, col))
            if coord:
                wall_strings.add(f"WALL {orientation} {coord}")
        return wall_strings

    def get_current_player(self):
        return self.current_player

    def get_opponent(self, player_id):
        return 2 if player_id == 1 else 1

    def get_winner(self):
        return self.winner

    def is_game_over(self):
        return self.winner is not None

    # --- Helper Methods ---
    def _is_on_board(self, pos):
        if pos is None or not isinstance(pos, tuple) or len(pos) != 2:
            return False
        row, col = pos
        return 0 <= row < self.board_size and 0 <= col < self.board_size

    def _is_move_blocked_by_wall(self, start_row, start_col, end_row, end_col):
        # Moving down
        if end_row > start_row:
            return ('H', start_row, start_col) in self.placed_walls or \
                   ('H', start_row, start_col - 1) in self.placed_walls
        # Moving up
        elif start_row > end_row:
            return ('H', end_row, start_col) in self.placed_walls or \
                   ('H', end_row, start_col - 1) in self.placed_walls
        # Moving right
        elif end_col > start_col:
            return ('V', start_row, start_col) in self.placed_walls or \
                   ('V', start_row - 1, start_col) in self.placed_walls
        # Moving left
        elif start_col > end_col:
            return ('V', start_row, end_col) in self.placed_walls or \
                   ('V', start_row - 1, end_col) in self.placed_walls
        return False

    # --- Pathfinding & Blocking Checks ---
    def _bfs_find_path(self, player_id):
        start_pos = self.pawn_positions.get(player_id)
        if not start_pos:
            return False
        goal_row = self.board_size - 1 if player_id == 1 else 0

        queue = collections.deque([start_pos])
        visited = {start_pos}

        while queue:
            current_row, current_col = queue.popleft()
            if current_row == goal_row:
                return True

            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                next_row, next_col = current_row + dr, current_col + dc
                next_pos = (next_row, next_col)
                if self._is_on_board(next_pos) and \
                   next_pos not in visited and not \
                   self._is_move_blocked_by_wall(current_row, current_col, next_row, next_col):
                    visited.add(next_pos)
                    queue.append(next_pos)
        return False

    def _check_if_path_blocked_by_wall(self, potential_wall):
        self.placed_walls.add(potential_wall)
        path_exists_p1 = self._bfs_find_path(1)
        path_exists_p2 = self._bfs_find_path(2)
        self.placed_walls.remove(potential_wall)
        return not (path_exists_p1 and path_exists_p2)

    def bfs_shortest_path_length(self, player_id):
        start_pos = self.pawn_positions.get(player_id)
        if not start_pos:
            return float('inf')
        goal_row = self.board_size - 1 if player_id == 1 else 0

        queue = collections.deque([(start_pos, 0)])
        visited = {start_pos}

        while queue:
            (current_row, current_col), distance = queue.popleft()
            if current_row == goal_row:
                return distance

            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                next_row, next_col = current_row + dr, current_col + dc
                next_pos = (next_row, next_col)
                if self._is_on_board(next_pos) and \
                   next_pos not in visited and not \
                   self._is_move_blocked_by_wall(current_row, current_col, next_row, next_col):
                    visited.add(next_pos)
                    queue.append((next_pos, distance + 1))
        return float('inf')

    # --- Pawn Move Validation ---
    def get_valid_pawn_moves(self, player_id):
        valid_moves = set()
        start_pos = self.pawn_positions.get(player_id)
        opponent_id = self.get_opponent(player_id)
        opponent_pos = self.pawn_positions.get(opponent_id)

        if self.is_game_over() or not start_pos or not opponent_pos:
            return valid_moves

        start_row, start_col = start_pos
        opp_row, opp_col = opponent_pos

        # Standard moves
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            target_row, target_col = start_row + dr, start_col + dc
            target_pos = (target_row, target_col)
            is_on_board = self._is_on_board(target_pos)
            is_opponent_square = (opponent_pos is not None and target_pos == opponent_pos)
            is_blocked = self._is_move_blocked_by_wall(start_row, start_col, target_row, target_col) if is_on_board else False
            if is_on_board and not is_opponent_square and not is_blocked:
                valid_moves.add(target_pos)

        # Jump moves
        is_opponent_adjacent = abs(start_row - opp_row) + abs(start_col - opp_col) == 1
        if is_opponent_adjacent:
            # Straight jump
            d_row_opp, d_col_opp = opp_row - start_row, opp_col - start_col
            jump_pos = (opp_row + d_row_opp, opp_col + d_col_opp)
            wall_behind_opponent = self._is_move_blocked_by_wall(opp_row, opp_col, jump_pos[0], jump_pos[1])

            if self._is_on_board(jump_pos) and not wall_behind_opponent:
                valid_moves.add(jump_pos)
            # Diagonal jump (if straight jump is blocked)
            else:
                side_moves = [(0, 1), (0, -1)] if d_col_opp == 0 else [(1, 0), (-1, 0)]
                for dr_diag, dc_diag in side_moves:
                    diag_pos = (opp_row + dr_diag, opp_col + dc_diag)
                    if self._is_on_board(diag_pos) and diag_pos != start_pos and not self._is_move_blocked_by_wall(opp_row, opp_col, diag_pos[0], diag_pos[1]):
                        valid_moves.add(diag_pos)
        return valid_moves

    def is_valid_pawn_move(self, player_id, target_pos):
        if target_pos is None or not self._is_on_board(target_pos):
            return False
        return target_pos in self.get_valid_pawn_moves(player_id)

    # --- Wall Placement Validation ---
    def check_wall_placement_validity(self, player_id, orientation, row, col):
        if self.walls_left.get(player_id, 0) <= 0:
            return False, R_WALL_NOWALLS
        if orientation not in ('H', 'V'):
            return False, R_INV_ORIENT
        if not (0 <= row < self.board_size - 1 and 0 <= col < self.board_size - 1):
            return False, R_WALL_OFFBOARD

        wall_to_place = (orientation, row, col)
        if wall_to_place in self.placed_walls:
            return False, R_WALL_OVERLAP

        # Check for conflicts with perpendicular or adjacent parallel walls
        if orientation == 'H':
            if ('V', row, col) in self.placed_walls or \
               ('H', row, col - 1) in self.placed_walls or \
               ('H', row, col + 1) in self.placed_walls:
                return False, R_WALL_CONFLICT
        else:  # orientation == 'V'
            if ('H', row, col) in self.placed_walls or \
               ('V', row - 1, col) in self.placed_walls or \
               ('V', row + 1, col) in self.placed_walls:
                return False, R_WALL_CONFLICT

        if self._check_if_path_blocked_by_wall(wall_to_place):
            return False, R_WALL_PATHBLOCK

        return True, R_OK

    def get_valid_wall_placements(self, player_id):
        valid_walls = []
        if self.get_walls_left(player_id) <= 0:
            return valid_walls

        for r in range(self.board_size - 1):
            for c in range(self.board_size - 1):
                coord = self._pos_to_coord((r, c))
                if not coord:
                    continue
                # Check Horizontal
                is_valid_h, _ = self.check_wall_placement_validity(player_id, 'H', r, c)
                if is_valid_h:
                    valid_walls.append(f"WALL H {coord}")
                # Check Vertical
                is_valid_v, _ = self.check_wall_placement_validity(player_id, 'V', r, c)
                if is_valid_v:
                    valid_walls.append(f"WALL V {coord}")
        return sorted(valid_walls)

    def _check_win_condition(self):
        if self.current_player not in self.pawn_positions:
            return
        pawn_row, _ = self.pawn_positions[self.current_player]
        if self.current_player == 1 and pawn_row == self.board_size - 1:
            self.winner = 1
        elif self.current_player == 2 and pawn_row == 0:
            self.winner = 2

    # --- Making Moves ---
    def make_move(self, move_string):
        if self.is_game_over():
            return False, R_GAMEOVER

        parts = move_string.strip().upper().split()
        if not parts or len(parts) < 2 or len(parts) > 3 or parts[0] not in ("MOVE", "WALL"):
            return False, R_INV_FORMAT

        move_type = parts[0]
        try:
            if move_type == "MOVE" and len(parts) == 2:
                return self._make_pawn_move(parts[1], move_string)
            elif move_type == "WALL" and len(parts) == 3:
                return self._make_wall_placement(parts[1], parts[2], move_string)
            else:
                return False, R_INV_FORMAT
        except Exception as e:
            print(f"!! Error processing move '{move_string}': {e}")
            traceback.print_exc()
            return False, f"InternalError: {e}"

    def _make_pawn_move(self, target_coord, move_string):
        target_pos = self._coord_to_pos(target_coord)
        if target_pos is None:
            return False, R_INV_COORD
        if not self._is_on_board(target_pos):
            return False, R_PAWN_OFFBOARD

        if not self.is_valid_pawn_move(self.current_player, target_pos):
            # Provide a more specific reason for failure
            start_pos = self.pawn_positions.get(self.current_player)
            opponent_pos = self.pawn_positions.get(self.get_opponent(self.current_player))
            reason = R_PAWN_NOTADJ
            if opponent_pos and target_pos == opponent_pos:
                reason = R_PAWN_OCCUPIED
            elif start_pos and abs(start_pos[0] - target_pos[0]) + abs(start_pos[1] - target_pos[1]) == 1 and \
                 self._is_move_blocked_by_wall(start_pos[0], start_pos[1], target_pos[0], target_pos[1]):
                reason = R_PAWN_WALLBLOCK
            return False, reason

        self.pawn_positions[self.current_player] = target_pos
        self._move_history.append(move_string)
        self._check_win_condition()
        if not self.is_game_over():
            self.current_player = self.get_opponent(self.current_player)
        return True, R_OK

    def _make_wall_placement(self, orientation, wall_coord, move_string):
        if orientation not in ('H', 'V'):
            return False, R_INV_ORIENT
        wall_pos = self._coord_to_pos(wall_coord)
        if wall_pos is None or not (0 <= wall_pos[0] < self.board_size - 1 and 0 <= wall_pos[1] < self.board_size - 1):
            return False, R_WALL_OFFBOARD

        row, col = wall_pos
        is_valid, reason = self.check_wall_placement_validity(self.current_player, orientation, row, col)
        if not is_valid:
            return False, reason

        self.placed_walls.add((orientation, row, col))
        self.walls_left[self.current_player] -= 1
        self._move_history.append(move_string)
        self.current_player = self.get_opponent(self.current_player)
        return True, R_OK


# --- Self-Tests ---
if __name__ == "__main__":
    print("--- Basic Move Tests ---")
    game = QuoridorGame()
    print("Initial state created.")
    result, reason = game.make_move("MOVE E2")
    print(f"MOVE E2: Success={result}, Reason={reason}")
    result, reason = game.make_move("MOVE E8")  # P2's turn now
    print(f"MOVE E8 (P2): Success={result}, Reason={reason}")
    # Invalid move for P1 now
    result, reason = game.make_move("MOVE E3")
    print(f"MOVE E3 (P1): Success={result}, Reason={reason}")
    print(f"P1 valid moves from E2: {[game._pos_to_coord(p) for p in sorted(list(game.get_valid_pawn_moves(1)))]}")

    print("\n--- Testing bfs_shortest_path_length ---")
    game_path = QuoridorGame()
    p1_len = game_path.bfs_shortest_path_length(1)
    p2_len = game_path.bfs_shortest_path_length(2)
    print(f"Initial state: P1 path={p1_len}, P2 path={p2_len}")
    game_path.make_move("MOVE E2")
    game_path.make_move("MOVE E8")
    p1_len = game_path.bfs_shortest_path_length(1)
    p2_len = game_path.bfs_shortest_path_length(2)
    print(f"After E2, E8: P1 path={p1_len}, P2 path={p2_len}")
    # Manually place a wall for testing
    game_path.placed_walls.add(('H', 1, 4))
    game_path.walls_left[1] -= 1
    game_path.current_player = 2  # Set turn to P2
    p1_len = game_path.bfs_shortest_path_length(1)
    p2_len = game_path.bfs_shortest_path_length(2)
    print(f"After P1 WALL H E2: P1 path={p1_len}, P2 path={p2_len}")

    print("\n--- Testing get_valid_wall_placements ---")
    game_walls = QuoridorGame()
    game_walls.make_move("MOVE E2")
    game_walls.make_move("MOVE E8")
    game_walls.placed_walls.add(('H', 4, 4)) # Wall at H E5
    game_walls.current_player = 1
    print(f"State: P1@E2, P2@E8, Wall H E5. Turn: {game_walls.current_player}")
    print(f"P1 Walls Left: {game_walls.get_walls_left(1)}")
    valid_walls_p1 = game_walls.get_valid_wall_placements(1)
    print(f"P1 Valid Walls ({len(valid_walls_p1)}): {valid_walls_p1[:10]}...")
    print(f"Is WALL H D5 valid? {'WALL H D5' in valid_walls_p1}")
    print(f"Is WALL V E5 valid? {'WALL V E5' in valid_walls_p1}")
    print(f"Is WALL H E4 (conflict) valid? {'WALL H E4' in valid_walls_p1}")
    result, reason = game_walls.make_move("WALL H E9")  # Off board
    print(f"P1 attempts WALL H E9: Success={result}, Reason={reason}")
    result, reason = game_walls.make_move("WALL H D5")
    print(f"P1 attempts WALL H D5: Success={result}, Reason={reason}")