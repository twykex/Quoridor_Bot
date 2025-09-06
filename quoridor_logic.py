# quoridor_logic.py (Fix _bfs_find_path scope)

import collections
import sys
import math
import copy

# sys.setrecursionlimit(2000)

BOARD_SIZE = 9
INITIAL_WALLS = 10

R_OK = None; R_GAMEOVER = "GameOver"; R_INV_FORMAT = "InvFormat"; R_INV_COORD = "InvCoord"
R_INV_ORIENT = "InvOrient"; R_PAWN_OFFBOARD = "PawnOffBoard"; R_PAWN_OCCUPIED = "PawnOccupied"
R_PAWN_WALLBLOCK = "PawnWallBlock"; R_PAWN_NOTADJ = "PawnNotAdjOrJump"; R_WALL_NOWALLS = "WallNoWalls"
R_WALL_OFFBOARD = "WallOffBoard"; R_WALL_OVERLAP = "WallOverlap"; R_WALL_CONFLICT = "WallConflict"
R_WALL_PATHBLOCK = "WallPathBlock"

class QuoridorGame:
    def __init__(self, num_players=2):
        self.board_size = BOARD_SIZE
        self.num_players = num_players
        if self.num_players == 2:
            self.pawn_positions = {1: (0, 4), 2: (8, 4)}
            self.walls_left = {1: 10, 2: 10}
            self.goal_conditions = {
                1: lambda r, c: r == self.board_size - 1,
                2: lambda r, c: r == 0
            }
        elif self.num_players == 4:
            self.pawn_positions = {1: (0, 4), 2: (8, 4), 3: (4, 0), 4: (4, 8)}
            self.walls_left = {1: 5, 2: 5, 3: 5, 4: 5}
            self.goal_conditions = {
                1: lambda r, c: r == self.board_size - 1,
                2: lambda r, c: r == 0,
                3: lambda r, c: c == self.board_size - 1,
                4: lambda r, c: c == 0
            }
        else:
            raise ValueError("Number of players must be 2 or 4")
        self.placed_walls = set()
        self.current_player = 1
        self.winner = None
        self._move_history = []

    # --- Coordinate Helpers ---
    def _coord_to_pos(self, coord_str):
        if not isinstance(coord_str, str) or len(coord_str) < 2: return None
        cc=coord_str[0].upper(); rs=coord_str[1:]
        if not ('A'<=cc<=chr(ord('A')+self.board_size-1)) or not rs.isdigit(): return None
        col=ord(cc)-ord('A'); row=int(rs)-1
        if not (0<=row<self.board_size and 0<=col<self.board_size): return None
        return row, col

    def _pos_to_coord(self, pos):
        if not isinstance(pos, tuple) or len(pos) != 2: return None
        r, c = pos
        if not (0<=r<self.board_size and 0<=c<self.board_size): return None
        return f"{chr(ord('A')+c)}{r+1}"

    # --- Getters ---
    def get_state_dict(self):
        state = {
            "board_size": self.board_size,
            "num_players": self.num_players,
            "pawn_positions": {p: self._pos_to_coord(pos) for p, pos in self.pawn_positions.items()},
            "walls_left": self.walls_left,
            "placed_walls": sorted(list(self.get_placed_wall_strings())),
            "current_player": self.current_player,
            "winner": self.winner,
            "is_game_over": self.is_game_over()
        }
        # For backward compatibility with 2-player UI
        if self.num_players == 2:
            state["p1_pos"] = self._pos_to_coord(self.pawn_positions.get(1))
            state["p2_pos"] = self._pos_to_coord(self.pawn_positions.get(2))
            state["p1_walls"] = self.walls_left.get(1)
            state["p2_walls"] = self.walls_left.get(2)
        return state

    def get_pawn_position(self, p): return self.pawn_positions.get(p)
    def get_pawn_coord(self, p): return self._pos_to_coord(self.get_pawn_position(p))
    def get_walls_left(self, p): return self.walls_left.get(p, 0)
    def get_placed_walls(self): return self.placed_walls.copy()
    def get_placed_wall_strings(self): ws=set(); [ws.add(f"WALL {o} {self._pos_to_coord((r, c))}") for o,r,c in self.placed_walls if self._pos_to_coord((r,c))]; return ws
    def get_current_player(self): return self.current_player
    def _get_next_player(self, player_id=None):
        if player_id is None: player_id = self.current_player
        return (player_id % self.num_players) + 1
    def get_winner(self): return self.winner
    def is_game_over(self): return self.winner is not None

    # --- Helper Methods ---
    def _is_on_board(self, pos):
        if pos is None: return False;
        if not isinstance(pos, tuple) or len(pos) != 2: return False
        r, c = pos; return 0 <= r < self.board_size and 0 <= c < self.board_size

    def _is_move_blocked_by_wall(self, r1, c1, r2, c2): # Simplified
        if r2>r1: return ('H',r1,c1) in self.placed_walls or ('H',r1,c1-1) in self.placed_walls
        elif r1>r2: return ('H',r2,c1) in self.placed_walls or ('H',r2,c1-1) in self.placed_walls
        elif c2>c1: return ('V',r1,c1) in self.placed_walls or ('V',r1-1,c1) in self.placed_walls
        elif c1>c2: return ('V',r1,c2) in self.placed_walls or ('V',r1-1,c2) in self.placed_walls
        return False

    # --- Pathfinding & Blocking Checks (Readable + BFS Fix) ---
    def _bfs_find_path(self, player_id): # Boolean check
        start_pos = self.pawn_positions.get(player_id)
        if not start_pos: return False
        goal_func = self.goal_conditions[player_id]
        queue = collections.deque([start_pos])
        visited = {start_pos}
        while queue:
            cr, cc = queue.popleft()
            if goal_func(cr, cc): return True
            for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
                nr, nc = cr + dr, cc + dc; next_pos = (nr, nc)
                if (self._is_on_board(next_pos) and next_pos not in visited and not self._is_move_blocked_by_wall(cr, cc, nr, nc)):
                    visited.add(next_pos); queue.append(next_pos)
        return False

    def _check_if_path_blocked(self, potential_wall): # Uses boolean BFS
        self.placed_walls.add(potential_wall)
        all_paths_exist = all(self._bfs_find_path(p) for p in range(1, self.num_players + 1))
        self.placed_walls.remove(potential_wall)
        return not all_paths_exist

    def bfs_shortest_path_length(self, player_id): # Returns length or inf
        start_pos = self.pawn_positions.get(player_id)
        if not start_pos: return float('inf')
        goal_func = self.goal_conditions[player_id]
        queue = collections.deque([(start_pos, 0)])
        visited = {start_pos}
        while queue:
            (cr, cc), distance = queue.popleft()
            if goal_func(cr, cc): return distance
            for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
                nr, nc = cr + dr, cc + dc; next_pos = (nr, nc)
                if (self._is_on_board(next_pos) and next_pos not in visited and not self._is_move_blocked_by_wall(cr, cc, nr, nc)):
                    visited.add(next_pos); queue.append((next_pos, distance + 1))
        return float('inf')

    # --- Pawn Move Validation (Readable) ---
    def get_valid_pawn_moves(self, player_id):
        valid_moves = set()
        start_pos = self.pawn_positions.get(player_id)
        if self.is_game_over() or not start_pos:
            return valid_moves
        r1, c1 = start_pos
        other_pawn_positions = {p: pos for p, pos in self.pawn_positions.items() if p != player_id}

        # Basic orthogonal moves
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            tr, tc = r1 + dr, c1 + dc
            target_pos = (tr, tc)
            if self._is_on_board(target_pos) and \
               target_pos not in other_pawn_positions.values() and \
               not self._is_move_blocked_by_wall(r1, c1, tr, tc):
                valid_moves.add(target_pos)

        # Jumps over opponents
        for opp_id, opp_pos in other_pawn_positions.items():
            if abs(r1 - opp_pos[0]) + abs(c1 - opp_pos[1]) == 1: # is adjacent
                # Check for wall between player and opponent
                if self._is_move_blocked_by_wall(r1, c1, opp_pos[0], opp_pos[1]):
                    continue

                dr_opp, dc_opp = opp_pos[0] - r1, opp_pos[1] - c1
                jump_pos = (opp_pos[0] + dr_opp, opp_pos[1] + dc_opp)

                if self._is_on_board(jump_pos) and not self._is_move_blocked_by_wall(opp_pos[0], opp_pos[1], jump_pos[0], jump_pos[1]):
                    if jump_pos not in self.pawn_positions.values():
                        valid_moves.add(jump_pos)
                    else: # The space behind opponent is occupied, check for diagonal jumps
                        # Horizontal jump blocked
                        if dr_opp == 0:
                            if self._is_on_board((opp_pos[0] + 1, opp_pos[1])) and not self._is_move_blocked_by_wall(opp_pos[0], opp_pos[1], opp_pos[0]+1, opp_pos[1]) and (opp_pos[0]+1, opp_pos[1]) not in self.pawn_positions.values(): valid_moves.add((opp_pos[0]+1, opp_pos[1]))
                            if self._is_on_board((opp_pos[0] - 1, opp_pos[1])) and not self._is_move_blocked_by_wall(opp_pos[0], opp_pos[1], opp_pos[0]-1, opp_pos[1]) and (opp_pos[0]-1, opp_pos[1]) not in self.pawn_positions.values(): valid_moves.add((opp_pos[0]-1, opp_pos[1]))
                        # Vertical jump blocked
                        elif dc_opp == 0:
                            if self._is_on_board((opp_pos[0], opp_pos[1] + 1)) and not self._is_move_blocked_by_wall(opp_pos[0], opp_pos[1], opp_pos[0], opp_pos[1]+1) and (opp_pos[0], opp_pos[1]+1) not in self.pawn_positions.values(): valid_moves.add((opp_pos[0], opp_pos[1]+1))
                            if self._is_on_board((opp_pos[0], opp_pos[1] - 1)) and not self._is_move_blocked_by_wall(opp_pos[0], opp_pos[1], opp_pos[0], opp_pos[1]-1) and (opp_pos[0], opp_pos[1]-1) not in self.pawn_positions.values(): valid_moves.add((opp_pos[0], opp_pos[1]-1))
        return valid_moves

    def is_valid_pawn_move(self, player_id, target_pos):
        if target_pos is None or not self._is_on_board(target_pos): return False
        return target_pos in self.get_valid_pawn_moves(player_id)

    # --- Wall Placement Validation (Readable) ---
    def check_wall_placement_validity(self, player_id, orientation, r, c):
        if self.walls_left.get(player_id,0)<=0: return False, R_WALL_NOWALLS;
        if orientation not in ('H','V'): return False, R_INV_ORIENT;
        if not (0<=r<self.board_size-1 and 0<=c<self.board_size-1): return False, R_WALL_OFFBOARD;
        wtp=(orientation,r,c);
        if wtp in self.placed_walls: return False, R_WALL_OVERLAP;
        if orientation=='H':
            if ('V',r,c) in self.placed_walls or ('H',r,c-1) in self.placed_walls or ('H',r,c+1) in self.placed_walls: return False, R_WALL_CONFLICT;
        else:
            if ('H',r,c) in self.placed_walls or ('V',r-1,c) in self.placed_walls or ('V',r+1,c) in self.placed_walls: return False, R_WALL_CONFLICT;
        if self._check_if_path_blocked(wtp): return False, R_WALL_PATHBLOCK;
        return True, R_OK

    def get_valid_wall_placements(self, player_id): # Readable + Fix
        vw=[]; wl=self.walls_left.get(player_id,0);
        if wl<=0: return vw;
        for r in range(self.board_size-1):
            for c in range(self.board_size-1):
                coord=self._pos_to_coord((r,c));
                if not coord: continue;
                is_vh,_=self.check_wall_placement_validity(player_id,'H',r,c);
                if is_vh: vw.append(f"WALL H {coord}")
                is_vv,_=self.check_wall_placement_validity(player_id,'V',r,c);
                if is_vv: vw.append(f"WALL V {coord}")
        return sorted(vw)

    def _check_win_condition(self):
        player = self.current_player
        if player not in self.pawn_positions: return
        r, c = self.pawn_positions[player]
        if self.goal_conditions[player](r, c):
            self.winner = player

    # --- Making Moves (Refined Reason Logic - Readable) ---
    def make_move(self, move_string):
        if self.is_game_over(): return False, R_GAMEOVER
        parts = move_string.strip().upper().split()
        if not parts or len(parts) < 2 or len(parts) > 3 or parts[0] not in ("MOVE", "WALL"): return False, R_INV_FORMAT
        move_type = parts[0]
        try:
            if move_type == "MOVE" and len(parts) == 2:
                target_coord = parts[1]; target_pos = self._coord_to_pos(target_coord)
                if target_pos is None: return False, R_INV_COORD
                if not self._is_on_board(target_pos): return False, R_PAWN_OFFBOARD

                is_valid = self.is_valid_pawn_move(self.current_player, target_pos)
                if not is_valid:
                    reason = R_PAWN_NOTADJ
                    if target_pos in self.pawn_positions.values(): reason = R_PAWN_OCCUPIED
                    else:
                        start_pos = self.pawn_positions.get(self.current_player)
                        if start_pos and abs(start_pos[0]-target_pos[0])+abs(start_pos[1]-target_pos[1])==1 and self._is_move_blocked_by_wall(start_pos[0],start_pos[1],target_pos[0],target_pos[1]):
                            reason = R_PAWN_WALLBLOCK
                    return False, reason

                self.pawn_positions[self.current_player] = target_pos; self._move_history.append(move_string); self._check_win_condition()
                if not self.is_game_over(): self.current_player = self._get_next_player()
                return True, R_OK

            elif move_type == "WALL" and len(parts) == 3:
                orientation, wall_coord = parts[1], parts[2]
                if orientation not in ('H', 'V'): return False, R_INV_ORIENT
                wall_pos = self._coord_to_pos(wall_coord)
                if wall_pos is None or not (0 <= wall_pos[0] < self.board_size - 1 and 0 <= wall_pos[1] < self.board_size - 1): return False, R_WALL_OFFBOARD
                r, c = wall_pos; is_valid, reason = self.check_wall_placement_validity(self.current_player, orientation, r, c)
                if not is_valid: return False, reason
                self.placed_walls.add((orientation, r, c)); self.walls_left[self.current_player] -= 1
                self._move_history.append(move_string); self.current_player = self._get_next_player()
                return True, R_OK
            else: return False, R_INV_FORMAT
        except Exception as e: print(f"!! Error processing move '{move_string}': {e}"); import traceback; traceback.print_exc(); return False, f"InternalError: {e}"

# --- Self-Tests (Readable) ---
if __name__ == "__main__":
    print("--- 4-Player Game Tests ---")
    game = QuoridorGame(num_players=4)
    print("Initial 4-player state created.")
    print(f"Pawn positions: {game.pawn_positions}")
    print(f"Walls left: {game.walls_left}")
    print(f"Current player: {game.current_player}")

    print("\n--- Testing bfs_shortest_path_length for 4 players ---")
    for i in range(1, 5):
        path_len = game.bfs_shortest_path_length(i)
        print(f"Initial state: P{i} path={path_len}")

    print("\n--- Basic Move Tests (4 players) ---")
    result, reason = game.make_move("MOVE E2"); print(f"P1 MOVE E2: Success={result}, Reason={reason}, Next Player: {game.current_player}")
    result, reason = game.make_move("MOVE E8"); print(f"P2 MOVE E8: Success={result}, Reason={reason}, Next Player: {game.current_player}")
    result, reason = game.make_move("MOVE B5"); print(f"P3 MOVE B5: Success={result}, Reason={reason}, Next Player: {game.current_player}")
    result, reason = game.make_move("MOVE H5"); print(f"P4 MOVE H5: Success={result}, Reason={reason}, Next Player: {game.current_player}")

    print(f"\nP1 valid moves from E2: {[game._pos_to_coord(p) for p in sorted(list(game.get_valid_pawn_moves(1)))]}")

    print("\n--- Testing Wall Placement ---")
    # It's P1's turn again
    result, reason = game.make_move("WALL H E2")
    print(f"P1 attempts WALL H E2: Success={result}, Reason={reason}, Next Player: {game.current_player}")
    print(f"P1 Walls Left: {game.get_walls_left(1)}")

    print("\n--- Testing Path Blocking ---")
    game_for_block_test = QuoridorGame(num_players=4)
    # This wall would block P1 if other walls were present
    game_for_block_test.placed_walls.add(('H', 0, 1)); game_for_block_test.placed_walls.add(('H', 0, 3)); game_for_block_test.placed_walls.add(('H', 0, 5)); game_for_block_test.placed_walls.add(('H', 0, 7))
    print(f"Blocking P1 path manually")
    is_blocked = game_for_block_test._check_if_path_blocked(('H', 0, 0))
    print(f"Is path blocked by wall at A1 for P1? {is_blocked}")


    print("\n--- Test a few more turns ---")
    game = QuoridorGame(num_players=4)
    game.make_move("MOVE E2") # P1
    game.make_move("MOVE E8") # P2
    game.make_move("MOVE B5") # P3
    game.make_move("MOVE H5") # P4
    game.make_move("MOVE E3") # P1
    game.make_move("MOVE E7") # P2
    game.make_move("MOVE C5") # P3
    game.make_move("MOVE G5") # P4
    print("Game state after a few turns:")
    print(game.get_state_dict())