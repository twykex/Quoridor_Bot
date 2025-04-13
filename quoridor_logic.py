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
    def __init__(self):
        self.board_size=BOARD_SIZE; self.walls_total=INITIAL_WALLS
        self.pawn_positions={ 1:(0,4), 2:(8,4) }; self.walls_left={1:10, 2:10}
        self.placed_walls=set(); self.current_player=1; self.winner=None; self._move_history=[]

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
    def get_state_dict(self): return {"board_size":self.board_size,"p1_pos":self._pos_to_coord(self.pawn_positions.get(1)),"p2_pos":self._pos_to_coord(self.pawn_positions.get(2)),"p1_walls":self.walls_left[1],"p2_walls":self.walls_left[2],"placed_walls":sorted(list(self.get_placed_wall_strings())),"current_player":self.current_player,"winner":self.winner,"is_game_over":self.is_game_over()}
    def get_pawn_position(self, p): return self.pawn_positions.get(p)
    def get_pawn_coord(self, p): return self._pos_to_coord(self.get_pawn_position(p))
    def get_walls_left(self, p): return self.walls_left.get(p, 0)
    def get_placed_walls(self): return self.placed_walls.copy()
    def get_placed_wall_strings(self): ws=set(); [ws.add(f"WALL {o} {self._pos_to_coord((r, c))}") for o,r,c in self.placed_walls if self._pos_to_coord((r,c))]; return ws
    def get_current_player(self): return self.current_player
    def get_opponent(self, p): return 2 if p == 1 else 1
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
        if not start_pos: return False # No start pos, no path
        goal_row = self.board_size - 1 if player_id == 1 else 0
        # --- FIX: Initialize q and visited before loop ---
        queue = collections.deque([start_pos])
        visited = {start_pos}
        # --- End FIX ---
        while queue: # Now 'queue' is guaranteed to exist
            cr, cc = queue.popleft()
            if cr == goal_row: return True
            for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
                nr, nc = cr + dr, cc + dc; next_pos = (nr, nc)
                if (self._is_on_board(next_pos) and next_pos not in visited and not self._is_move_blocked_by_wall(cr, cc, nr, nc)):
                    visited.add(next_pos); queue.append(next_pos)
        return False # Queue emptied, goal not reached

    def _check_if_path_blocked(self, potential_wall): # Uses boolean BFS
        self.placed_walls.add(potential_wall); path1 = self._bfs_find_path(1); path2 = self._bfs_find_path(2)
        self.placed_walls.remove(potential_wall); return not (path1 and path2)

    def bfs_shortest_path_length(self, player_id): # Returns length or inf
        start_pos = self.pawn_positions.get(player_id)
        if not start_pos: return float('inf')
        goal_row = self.board_size - 1 if player_id == 1 else 0
        # --- FIX: Initialize q and visited before loop ---
        queue = collections.deque([(start_pos, 0)])
        visited = {start_pos}
        # --- End FIX ---
        while queue: # Now 'queue' is guaranteed to exist
            (cr, cc), distance = queue.popleft()
            if cr == goal_row: return distance
            for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
                nr, nc = cr + dr, cc + dc; next_pos = (nr, nc)
                if (self._is_on_board(next_pos) and next_pos not in visited and not self._is_move_blocked_by_wall(cr, cc, nr, nc)):
                    visited.add(next_pos); queue.append((next_pos, distance + 1))
        return float('inf')

    # --- Pawn Move Validation (Readable) ---
    def get_valid_pawn_moves(self, player_id):
        valid_moves=set(); sp=self.pawn_positions.get(player_id); opp_id=self.get_opponent(player_id); op=self.pawn_positions.get(opp_id)
        if self.is_game_over() or not sp or not op: return valid_moves
        r1,c1=sp; opp_r,opp_c=op;
        for dr,dc in [(0,1),(0,-1),(1,0),(-1,0)]: # Orthogonal
            tr,tc=r1+dr,c1+dc; tp=(tr,tc);
            on_b=self._is_on_board(tp); is_o=(op is not None and tp==op); is_b=self._is_move_blocked_by_wall(r1,c1,tr,tc) if on_b else False;
            if not on_b or is_o or is_b: continue
            valid_moves.add(tp)
        is_adj=abs(r1-opp_r)+abs(c1-opp_c)==1
        if is_adj: # Jumps
            dr_o,dc_o=opp_r-r1,opp_c-c1; sj_p=(opp_r+dr_o,opp_c+dc_o); sj_c=False
            if self._is_on_board(sj_p) and not self._is_move_blocked_by_wall(opp_r,opp_c,sj_p[0],sj_p[1]): valid_moves.add(sj_p); sj_c=True
            if not sj_c:
                 side=[(0,1),(0,-1)] if dc_o==0 else [(1,0),(-1,0)];
                 for dr_d,dc_d in side:
                     dt_p=(opp_r+dr_d,opp_c+dc_d);
                     if self._is_on_board(dt_p) and dt_p!=sp and not self._is_move_blocked_by_wall(opp_r,opp_c,dt_p[0],dt_p[1]): valid_moves.add(dt_p)
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
        if self.current_player not in self.pawn_positions: return
        pr,_=self.pawn_positions[self.current_player];
        if self.current_player==1 and pr==self.board_size-1: self.winner=1;
        elif self.current_player==2 and pr==0: self.winner=2;

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
                    start_pos=self.pawn_positions.get(self.current_player); opp_id=self.get_opponent(self.current_player); opponent_pos=self.pawn_positions.get(opp_id)
                    reason = R_PAWN_NOTADJ
                    if opponent_pos and target_pos == opponent_pos: reason = R_PAWN_OCCUPIED
                    elif start_pos and abs(start_pos[0]-target_pos[0])+abs(start_pos[1]-target_pos[1])==1 and self._is_move_blocked_by_wall(start_pos[0],start_pos[1],target_pos[0],target_pos[1]): reason = R_PAWN_WALLBLOCK
                    return False, reason

                self.pawn_positions[self.current_player] = target_pos; self._move_history.append(move_string); self._check_win_condition()
                if not self.is_game_over(): self.current_player = self.get_opponent(self.current_player)
                return True, R_OK

            elif move_type == "WALL" and len(parts) == 3:
                orientation, wall_coord = parts[1], parts[2]
                if orientation not in ('H', 'V'): return False, R_INV_ORIENT
                wall_pos = self._coord_to_pos(wall_coord)
                if wall_pos is None or not (0 <= wall_pos[0] < self.board_size - 1 and 0 <= wall_pos[1] < self.board_size - 1): return False, R_WALL_OFFBOARD
                r, c = wall_pos; is_valid, reason = self.check_wall_placement_validity(self.current_player, orientation, r, c)
                if not is_valid: return False, reason
                self.placed_walls.add((orientation, r, c)); self.walls_left[self.current_player] -= 1
                self._move_history.append(move_string); self.current_player = self.get_opponent(self.current_player)
                return True, R_OK
            else: return False, R_INV_FORMAT
        except Exception as e: print(f"!! Error processing move '{move_string}': {e}"); import traceback; traceback.print_exc(); return False, f"InternalError: {e}"

# --- Self-Tests (Readable) ---
if __name__ == "__main__":
    print("--- Basic Move Tests ---")
    game = QuoridorGame(); print("Initial state created.")
    result, reason = game.make_move("MOVE E2"); print(f"MOVE E2: Success={result}, Reason={reason}")
    result, reason = game.make_move("MOVE E9"); print(f"MOVE E9 (P2): Success={result}, Reason={reason}")
    result, reason = game.make_move("MOVE E8"); print(f"MOVE E8 (P2): Success={result}, Reason={reason}")
    print(f"P1 valid moves from E2: {[game._pos_to_coord(p) for p in sorted(list(game.get_valid_pawn_moves(1)))]}")

    print("\n--- Testing bfs_shortest_path_length ---")
    game_path=QuoridorGame(); p1_len=game_path.bfs_shortest_path_length(1); p2_len=game_path.bfs_shortest_path_length(2); print(f"Initial state: P1 path={p1_len}, P2 path={p2_len}")
    game_path.make_move("MOVE E2"); game_path.make_move("MOVE E8")
    p1_len=game_path.bfs_shortest_path_length(1); p2_len=game_path.bfs_shortest_path_length(2); print(f"After E2, E8: P1 path={p1_len}, P2 path={p2_len}")
    game_path.placed_walls.add(('H', 1, 4)); game_path.walls_left[1] -= 1; game_path.current_player = 2
    p1_len=game_path.bfs_shortest_path_length(1); p2_len=game_path.bfs_shortest_path_length(2); print(f"After P1 WALL H E2: P1 path={p1_len}, P2 path={p2_len}")

    print("\n--- Testing get_valid_wall_placements ---")
    game_walls=QuoridorGame(); game_walls.make_move("MOVE E2"); game_walls.make_move("MOVE E8")
    game_walls.placed_walls.add(('H', 4, 4)); game_walls.current_player = 1
    print(f"State: P1@E2, P2@E8, Wall H E5. Turn: {game_walls.current_player}"); print(f"P1 Walls Left: {game_walls.get_walls_left(1)}")
    valid_walls_p1 = game_walls.get_valid_wall_placements(1); print(f"P1 Valid Walls ({len(valid_walls_p1)}): {valid_walls_p1[:10]}...")
    print(f"Is WALL H D5 valid? {'WALL H D5' in valid_walls_p1}"); print(f"Is WALL V E5 valid? {'WALL V E5' in valid_walls_p1}"); print(f"Is WALL H E4 valid? {'WALL H E4' in valid_walls_p1}")
    result, reason = game_walls.make_move("WALL H E9"); print(f"P1 attempts WALL H E9: Success={result}, Reason={reason}")
    result, reason = game_walls.make_move("WALL H D5"); print(f"P1 attempts WALL H D5: Success={result}, Reason={reason}")