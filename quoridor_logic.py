# quoridor_logic.py (Refactored for Undo/Redo and Readability)

import collections
import sys
import math

# Game constants
BOARD_SIZE = 9
INITIAL_WALLS = 10

# --- Reason Codes for Invalid Moves ---
R_OK = "OK"
R_GAMEOVER = "GameOver"
R_INV_FORMAT = "InvalidFormat"
R_INV_COORD = "InvalidCoordinate"
R_INV_ORIENT = "InvalidOrientation"
R_PAWN_OFFBOARD = "PawnOffBoard"
R_PAWN_OCCUPIED = "PawnOccupiedByOpponent"
R_PAWN_WALLBLOCK = "PawnBlockedByWall"
R_PAWN_NOTADJ = "PawnNotAdjacentOrValidJump"
R_WALL_NOWALLS = "NoWallsLeft"
R_WALL_OFFBOARD = "WallOffBoard"
R_WALL_OVERLAP = "WallOverlapsExisting"
R_WALL_CONFLICT = "WallConflictsWithNeighbor"
R_WALL_PATHBLOCK = "WallBlocksPathToGoal"


class QuoridorGame:
    def __init__(self):
        self.board_size = BOARD_SIZE
        self.walls_total = INITIAL_WALLS
        self.pawn_positions = {1: (0, 4), 2: (8, 4)}
        self.walls_left = {1: INITIAL_WALLS, 2: INITIAL_WALLS}
        self.placed_walls = set()
        self.current_player = 1
        self.winner = None
        self._move_history = []

    # --- Coordinate Helpers ---
    def _coord_to_pos(self, coord_str):
        if not isinstance(coord_str, str) or len(coord_str) < 2: return None
        col_char = coord_str[0].upper()
        row_str = coord_str[1:]
        if not ('A' <= col_char <= chr(ord('A') + self.board_size - 1)) or not row_str.isdigit(): return None
        col = ord(col_char) - ord('A')
        row = int(row_str) - 1
        if not (0 <= row < self.board_size and 0 <= col < self.board_size): return None
        return row, col

    def _pos_to_coord(self, pos):
        if not isinstance(pos, tuple) or len(pos) != 2: return None
        row, col = pos
        if not (0 <= row < self.board_size and 0 <= col < self.board_size): return None
        return f"{chr(ord('A') + col)}{row + 1}"

    # --- Getters ---
    def get_state_dict(self):
        return {
            "board_size": self.board_size,
            "p1_pos": self._pos_to_coord(self.pawn_positions.get(1)),
            "p2_pos": self._pos_to_coord(self.pawn_positions.get(2)),
            "p1_walls": self.walls_left[1],
            "p2_walls": self.walls_left[2],
            "placed_walls": sorted(list(self.get_placed_wall_strings())),
            "current_player": self.current_player,
            "winner": self.winner,
            "is_game_over": self.is_game_over()
        }

    def get_pawn_position(self, player_id): return self.pawn_positions.get(player_id)
    def get_pawn_coord(self, player_id): return self._pos_to_coord(self.get_pawn_position(player_id))
    def get_walls_left(self, player_id): return self.walls_left.get(player_id, 0)
    def get_placed_walls(self): return self.placed_walls.copy()
    def get_placed_wall_strings(self):
        wall_strings = set()
        for orientation, r, c in self.placed_walls:
            coord = self._pos_to_coord((r, c))
            if coord: wall_strings.add(f"WALL {orientation} {coord}")
        return wall_strings
    def get_current_player(self): return self.current_player
    def get_opponent(self, player_id): return 2 if player_id == 1 else 1
    def get_winner(self): return self.winner
    def is_game_over(self): return self.winner is not None

    # --- Helper Methods ---
    def _is_on_board(self, pos):
        if pos is None or not isinstance(pos, tuple) or len(pos) != 2: return False
        row, col = pos
        return 0 <= row < self.board_size and 0 <= col < self.board_size

    def _is_move_blocked_by_wall(self, r1, c1, r2, c2):
        if r2 > r1: return ('H', r1, c1) in self.placed_walls or ('H', r1, c1 - 1) in self.placed_walls
        elif r1 > r2: return ('H', r2, c1) in self.placed_walls or ('H', r2, c1 - 1) in self.placed_walls
        elif c2 > c1: return ('V', r1, c1) in self.placed_walls or ('V', r1 - 1, c1) in self.placed_walls
        elif c1 > c2: return ('V', r1, c2) in self.placed_walls or ('V', r1 - 1, c2) in self.placed_walls
        return False

    # --- Pathfinding & Blocking Checks ---
    def _bfs_find_path(self, player_id):
        start_pos = self.pawn_positions.get(player_id)
        if not start_pos: return False
        goal_row = self.board_size - 1 if player_id == 1 else 0
        queue = collections.deque([start_pos])
        visited = {start_pos}
        while queue:
            curr_row, curr_col = queue.popleft()
            if curr_row == goal_row: return True
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                next_pos = (curr_row + dr, curr_col + dc)
                if self._is_on_board(next_pos) and next_pos not in visited and not self._is_move_blocked_by_wall(curr_row, curr_col, next_pos[0], next_pos[1]):
                    visited.add(next_pos)
                    queue.append(next_pos)
        return False

    def _check_if_path_blocked(self, potential_wall):
        self.placed_walls.add(potential_wall)
        path1_exists = self._bfs_find_path(1)
        path2_exists = self._bfs_find_path(2)
        self.placed_walls.remove(potential_wall)
        return not (path1_exists and path2_exists)

    def bfs_shortest_path_length(self, player_id):
        start_pos = self.pawn_positions.get(player_id)
        if not start_pos: return float('inf')
        goal_row = self.board_size - 1 if player_id == 1 else 0
        queue = collections.deque([(start_pos, 0)])
        visited = {start_pos}
        while queue:
            (curr_row, curr_col), distance = queue.popleft()
            if curr_row == goal_row: return distance
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                next_pos = (curr_row + dr, curr_col + dc)
                if self._is_on_board(next_pos) and next_pos not in visited and not self._is_move_blocked_by_wall(curr_row, curr_col, next_pos[0], next_pos[1]):
                    visited.add(next_pos)
                    queue.append((next_pos, distance + 1))
        return float('inf')

    # --- Pawn Move Validation ---
    def get_valid_pawn_moves(self, player_id):
        valid_moves = set()
        start_pos = self.pawn_positions.get(player_id)
        opponent_pos = self.pawn_positions.get(self.get_opponent(player_id))
        if self.is_game_over() or not start_pos or not opponent_pos: return valid_moves

        r1, c1 = start_pos
        opp_r, opp_c = opponent_pos

        # Standard orthogonal moves
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            target_pos = (r1 + dr, c1 + dc)
            if self._is_on_board(target_pos) and target_pos != opponent_pos and not self._is_move_blocked_by_wall(r1, c1, target_pos[0], target_pos[1]):
                valid_moves.add(target_pos)

        # Jump moves
        is_adjacent = abs(r1 - opp_r) + abs(c1 - opp_c) == 1
        if is_adjacent and not self._is_move_blocked_by_wall(r1, c1, opp_r, opp_c):
            # Straight jump
            dr_o, dc_o = opp_r - r1, opp_c - c1
            straight_jump_pos = (opp_r + dr_o, opp_c + dc_o)
            if self._is_on_board(straight_jump_pos) and not self._is_move_blocked_by_wall(opp_r, opp_c, straight_jump_pos[0], straight_jump_pos[1]):
                valid_moves.add(straight_jump_pos)
            # Diagonal jumps (if straight jump is blocked by a wall)
            else:
                side_moves = [(0, 1), (0, -1)] if dc_o == 0 else [(1, 0), (-1, 0)]
                for dr_d, dc_d in side_moves:
                    diag_jump_pos = (opp_r + dr_d, opp_c + dc_d)
                    if self._is_on_board(diag_jump_pos) and diag_jump_pos != start_pos and not self._is_move_blocked_by_wall(opp_r, opp_c, diag_jump_pos[0], diag_jump_pos[1]):
                        valid_moves.add(diag_jump_pos)
        return valid_moves

    def is_valid_pawn_move(self, player_id, target_pos):
        if target_pos is None or not self._is_on_board(target_pos): return False
        return target_pos in self.get_valid_pawn_moves(player_id)

    # --- Wall Placement Validation ---
    def check_wall_placement_validity(self, player_id, orientation, r, c):
        if self.walls_left.get(player_id, 0) <= 0: return False, R_WALL_NOWALLS
        if orientation not in ('H', 'V'): return False, R_INV_ORIENT
        if not (0 <= r < self.board_size - 1 and 0 <= c < self.board_size - 1): return False, R_WALL_OFFBOARD

        wall_to_place = (orientation, r, c)
        if wall_to_place in self.placed_walls: return False, R_WALL_OVERLAP

        if orientation == 'H':
            if ('V', r, c) in self.placed_walls or ('H', r, c - 1) in self.placed_walls or ('H', r, c + 1) in self.placed_walls:
                return False, R_WALL_CONFLICT
        else:  # Vertical
            if ('H', r, c) in self.placed_walls or ('V', r - 1, c) in self.placed_walls or ('V', r + 1, c) in self.placed_walls:
                return False, R_WALL_CONFLICT

        if self._check_if_path_blocked(wall_to_place): return False, R_WALL_PATHBLOCK
        return True, R_OK

    def get_valid_wall_placements(self, player_id):
        valid_walls = []
        if self.walls_left.get(player_id, 0) <= 0: return valid_walls
        for r in range(self.board_size - 1):
            for c in range(self.board_size - 1):
                coord = self._pos_to_coord((r, c))
                if not coord: continue
                is_valid_h, _ = self.check_wall_placement_validity(player_id, 'H', r, c)
                if is_valid_h: valid_walls.append(f"WALL H {coord}")
                is_valid_v, _ = self.check_wall_placement_validity(player_id, 'V', r, c)
                if is_valid_v: valid_walls.append(f"WALL V {coord}")
        return sorted(valid_walls)

    def _check_win_condition(self):
        player_pos = self.pawn_positions.get(self.current_player)
        if not player_pos: return

        player_row, _ = player_pos
        if self.current_player == 1 and player_row == self.board_size - 1: self.winner = 1
        elif self.current_player == 2 and player_row == 0: self.winner = 2

    # --- Making & Undoing Moves ---
    def make_move(self, move_string):
        if self.is_game_over(): return False, R_GAMEOVER

        parts = move_string.strip().upper().split()
        if not parts or len(parts) < 2 or len(parts) > 3 or parts[0] not in ("MOVE", "WALL"):
            return False, R_INV_FORMAT

        move_type = parts[0]
        player = self.current_player

        try:
            if move_type == "MOVE" and len(parts) == 2:
                target_coord = parts[1]
                target_pos = self._coord_to_pos(target_coord)
                if target_pos is None: return False, R_INV_COORD
                if not self._is_on_board(target_pos): return False, R_PAWN_OFFBOARD

                if not self.is_valid_pawn_move(player, target_pos):
                    # Provide more specific reason for failure
                    start_pos = self.pawn_positions.get(player)
                    opponent_pos = self.pawn_positions.get(self.get_opponent(player))
                    reason = R_PAWN_NOTADJ
                    if opponent_pos and target_pos == opponent_pos: reason = R_PAWN_OCCUPIED
                    elif start_pos and abs(start_pos[0]-target_pos[0])+abs(start_pos[1]-target_pos[1])==1 and self._is_move_blocked_by_wall(start_pos[0],start_pos[1],target_pos[0],target_pos[1]): reason = R_PAWN_WALLBLOCK
                    return False, reason

                # Apply move
                old_pos = self.pawn_positions[player]
                self.pawn_positions[player] = target_pos
                self._move_history.append(move_string)
                self._check_win_condition()

                move_obj = {'type': 'MOVE', 'player': player, 'old_pos': old_pos, 'new_pos': target_pos, 'winner': self.winner}

                if not self.is_game_over(): self.current_player = self.get_opponent(player)
                return True, move_obj

            elif move_type == "WALL" and len(parts) == 3:
                orientation, wall_coord = parts[1], parts[2]
                wall_pos = self._coord_to_pos(wall_coord)
                if wall_pos is None or not (0 <= wall_pos[0] < self.board_size - 1 and 0 <= wall_pos[1] < self.board_size - 1):
                    return False, R_WALL_OFFBOARD

                is_valid, reason = self.check_wall_placement_validity(player, orientation, wall_pos[0], wall_pos[1])
                if not is_valid: return False, reason

                # Apply wall placement
                wall = (orientation, wall_pos[0], wall_pos[1])
                self.placed_walls.add(wall)
                self.walls_left[player] -= 1
                self._move_history.append(move_string)

                move_obj = {'type': 'WALL', 'player': player, 'wall': wall}

                self.current_player = self.get_opponent(player)
                return True, move_obj

            else:
                return False, R_INV_FORMAT
        except Exception as e:
            print(f"!! Error processing move '{move_string}': {e}")
            import traceback
            traceback.print_exc()
            return False, f"InternalError: {e}"

    def undo_move(self, move_obj):
        """ Reverts a move made on the board using a move object from make_move. """
        if not isinstance(move_obj, dict) or 'type' not in move_obj:
            raise ValueError("Invalid move object for undo.")

        player = move_obj['player']
        self.current_player = player # Restore the player who made the move
        self._move_history.pop() # Remove the last move string

        if move_obj['type'] == 'MOVE':
            self.pawn_positions[player] = move_obj['old_pos']
            self.winner = None # Always revert winner status on undo

        elif move_obj['type'] == 'WALL':
            self.placed_walls.remove(move_obj['wall'])
            self.walls_left[player] += 1

        else:
            raise ValueError(f"Unknown move type in move object: {move_obj['type']}")

# (Self-tests moved to tests/test_game.py)