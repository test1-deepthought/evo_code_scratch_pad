"""
PrologReasoning6 Agent - Adaptive maze explorer with Level 1+ traversal.

Key fixes over v5:
  FIX12: Dynamic wall color detection (scan grid borders, don't hardcode WALL_COLOR=4)
  FIX13: Reordered tile classification (special tiles checked BEFORE wall check)
  FIX14: Anti-loop stuck detection (track action history, break same-action loops)
  FIX15: Player position fallback cascade (pixel/frame-diff/visited-center/grid-center)
  FIX16: Multi-color adaptive thresholds (detect wall/floor colors dynamically from edges)
  FIX17: v4 Prolog rules with PLAYER_UNKNOWN handling and optimized BFS
"""

from __future__ import annotations
import logging, os, random, subprocess, tempfile, time
from collections import deque, Counter
from pathlib import Path
from typing import Any, Optional
import numpy as np
from arcengine import FrameData, GameAction, GameState
from ..agent import Agent

logger = logging.getLogger(__name__)
SWIPL_PATH = os.environ.get("SWIPL_PATH", "C:\\Program Files\\swipl\\bin\\swipl.exe")
PROLOG_DIR = Path(__file__).parent / "prolog"
ARC_RULES_V4_PL = PROLOG_DIR / "arc_rules_v4.pl"
TIMEOUT_SECONDS = 10
TILE_SIZE = 5
GRID_TILES_X = 13
GRID_TILES_Y = 13
_TILE_WALL = 4
_TILE_FLOOR = 100
_TILE_BORDER = 5
_TILE_PLAYER = 99
_TILE_PORTAL = 88
_TILE_MODIFIER = 77
_TILE_PLATFORM = 11
_TILE_UNKNOWN = 0
DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]
DIR_NAMES = ["UP", "DOWN", "LEFT", "RIGHT"]
DIR_ACTIONS = [GameAction.ACTION1, GameAction.ACTION2,
               GameAction.ACTION3, GameAction.ACTION4]


def _find_swipl() -> str:
    for cmd in [SWIPL_PATH, "C:\\Program Files\\swipl\\bin\\swipl.exe",
                "C:\\Program Files (x86)\\swipl\\bin\\swipl.exe", "swipl"]:
        try:
            r = subprocess.run([cmd, "--version"], capture_output=True,
                               text=True, timeout=5)
            if r.returncode == 0:
                return cmd
        except Exception:
            continue
    return ""


class PrologReasoning6(Agent):
    """ARC-AGI-3 agent with adaptive maze exploration for Level 1+."""

    MAX_ACTIONS: int = 500

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        raw_seed = int(time.time() * 1_000_000) + hash(self.game_id) % 1_000_000
        self._seed = abs(raw_seed) % (2**32)
        random.seed(self._seed)
        np.random.seed(self._seed)
        self._prolog_cmd = _find_swipl()
        self._has_prolog = bool(self._prolog_cmd)
        self._wall_colors: set[int] = set()
        self._floor_colors: set[int] = set()
        self._action_history: list[str] = []
        self._same_action_count = 0
        self._last_same_action: Optional[str] = None
        self._forced_alternation = False
        self._alternation_index = 0
        self._color_samples_taken = False
        self._clear_all_state()

    @property
    def name(self) -> str:
        return f"{super().name}.prolog6"

    def _clear_all_state(self) -> None:
        self._prev_grid: Optional[np.ndarray] = None
        self._player_pixel: Optional[tuple[int, int]] = None
        self._player_tile: Optional[tuple[int, int]] = None
        self._wall_tiles: set[tuple[int, int]] = set()
        self._visited_tiles: set[tuple[int, int]] = set()
        self._portal_tiles: dict[tuple[int, int], str] = {}
        self._modifier_tiles: dict[tuple[int, int], str] = {}
        self._had_modifier = False
        self._action_count = 0
        self._consecutive_stuck = 0
        self._interact_cooldown = 0
        self._best_levels = 0
        self._frame_count = 0
        self._pos_stack: list[tuple[int, int]] = []
        self._backtrack_mode = False
        self._sweep_direction = 2
        self._corridor_probe_counter = 0
        self._action_history.clear()
        self._same_action_count = 0
        self._last_same_action = None
        self._forced_alternation = False

    @staticmethod
    def _get_grid(frame):
        if not frame or not frame[0]:
            return np.zeros((64, 64), dtype=np.int32)
        return np.array(frame[-1] if len(frame) > 1 else frame[0], dtype=np.int32)

    @staticmethod
    def _pixel_to_tile(px: int, py: int) -> tuple[int, int]:
        return (px // TILE_SIZE, py // TILE_SIZE)

    # ------------------------------------------------------------------
    # FIX12: Dynamic wall/floor color detection by scanning grid edges
    # ------------------------------------------------------------------

    def _sample_colors(self, grid: np.ndarray) -> None:
        """FIX12: Scan grid edges to determine wall/floor colors dynamically."""
        if self._color_samples_taken:
            return
        h, w = grid.shape
        edge_counts: Counter = Counter()
        for x in range(w):
            edge_counts[grid[0, x]] += 1
            edge_counts[grid[h-1, x]] += 1
        for y in range(h):
            edge_counts[grid[y, 0]] += 1
            edge_counts[grid[y, w-1]] += 1

        if not edge_counts:
            self._wall_colors = {4, 5}
            return

        total_edge = 2 * (h + w)
        for color, count in edge_counts.most_common(5):
            if count / total_edge > 0.03 and color > 0:
                self._wall_colors.add(int(color))

        # Sample center for floor colors
        cx, cy = w // 2, h // 2
        center = grid[max(0,cy-5):min(h,cy+6), max(0,cx-5):min(w,cx+6)]
        if center.size > 0:
            center_counts = Counter(center.flatten().tolist())
            for color, count in center_counts.most_common(5):
                if int(color) not in self._wall_colors and color > 0:
                    if count / center.size > 0.1:
                        self._floor_colors.add(int(color))

        if not self._wall_colors:
            self._wall_colors = {4, 5}
        if not self._floor_colors:
            self._floor_colors = {3}
        logger.info(f"FIX12: walls={self._wall_colors} floors={self._floor_colors}")
        self._color_samples_taken = True

    # ------------------------------------------------------------------
    # FIX15: Player detection with fallback cascade
    # ------------------------------------------------------------------

    def _find_player_pixel(self, grid: np.ndarray) -> Optional[tuple[int, int]]:
        h, w = grid.shape
        best_score, best_pos = 0, None
        for y in range(h - 4):
            for x in range(w - 4):
                region = grid[y:y+5, x:x+5]
                orange = int((region[0:2, :] == 12).sum())
                blue = int((region[2:5, :] == 9).sum())
                red = int((region == 8).sum())
                if orange >= 2 and blue >= 3 and red < 8:
                    score = orange * 10 + blue * 10
                    if score > best_score:
                        best_score = score
                        best_pos = (x + 2, y + 2)
        return best_pos

    def _find_player_frame_diff(self, grid: np.ndarray) -> Optional[tuple[int, int]]:
        if self._prev_grid is None:
            return None
        diff = (grid != self._prev_grid)
        changed = np.where(diff)
        if len(changed[0]) < 4:
            return None
        my, mx = int(changed[0].min()), int(changed[1].min())
        My, Mx = int(changed[0].max()), int(changed[1].max())
        h, w = My - my + 1, Mx - mx + 1
        if 3 <= h <= 10 and 3 <= w <= 10:
            region = grid[my:My+1, mx:Mx+1]
            if int((region == 12).sum()) >= 1 or int((region == 9).sum()) >= 2:
                return ((mx + Mx) // 2, (my + My) // 2)
        return None

    def _find_player(self, grid: np.ndarray) -> Optional[tuple[int, int]]:
        pos = self._find_player_pixel(grid)
        if pos:
            return pos
        pos = self._find_player_frame_diff(grid)
        if pos:
            return pos
        if self._player_pixel and self._consecutive_stuck < 30:
            return self._player_pixel
        if self._visited_tiles:
            avg_x = sum(tx for tx, ty in self._visited_tiles) / len(self._visited_tiles)
            avg_y = sum(ty for tx, ty in self._visited_tiles) / len(self._visited_tiles)
            return (int(avg_x * TILE_SIZE + 2), int(avg_y * TILE_SIZE + 2))
        return (32, 32)

    # ------------------------------------------------------------------
    # FIX13+FIX16: Adaptive tile grid, special tiles checked BEFORE walls
    # ------------------------------------------------------------------

    def _build_tile_grid(self, grid: np.ndarray) -> np.ndarray:
        tile_grid = np.zeros((GRID_TILES_Y, GRID_TILES_X), dtype=np.int32)
        if not self._color_samples_taken:
            self._sample_colors(grid)
        wc = self._wall_colors or {4, 5}
        fc = self._floor_colors or {3}

        for ty in range(GRID_TILES_Y):
            for tx in range(GRID_TILES_X):
                ps, py_s = tx * TILE_SIZE, ty * TILE_SIZE
                region = grid[py_s:py_s+TILE_SIZE, ps:ps+TILE_SIZE]
                total = region.size
                if total == 0:
                    continue

                # FIX13: Player FIRST
                if int((region == 12).sum()) >= 2 and int((region == 9).sum()) >= 2:
                    tile_grid[ty, tx] = _TILE_PLAYER
                    continue
                # Portal
                if int((region == 8).sum()) / total > 0.15 or int((region == 1).sum()) / total > 0.2:
                    tile_grid[ty, tx] = _TILE_PORTAL
                    continue
                # Modifier
                if int((region == 14).sum()) / total > 0.1:
                    tile_grid[ty, tx] = _TILE_MODIFIER
                    continue
                # Platform
                if int((region == 11).sum()) / total > 0.3:
                    tile_grid[ty, tx] = _TILE_PLATFORM
                    continue
                # FIX16: Wall check with dynamic colors
                wall_ratio = sum(int((region == c).sum()) for c in wc) / total
                if wall_ratio > 0.25:
                    tile_grid[ty, tx] = _TILE_WALL
                    continue
                # Floor
                floor_ratio = sum(int((region == c).sum()) for c in fc) / total
                if floor_ratio > 0.15:
                    tile_grid[ty, tx] = _TILE_FLOOR
                elif int((region == 5).sum()) / total > 0.2:
                    tile_grid[ty, tx] = _TILE_BORDER
        return tile_grid

    # ------------------------------------------------------------------
    # Portal/modifier pixel scanning
    # ------------------------------------------------------------------

    def _scan_portals_pixel(self, grid: np.ndarray) -> None:
        h, w = grid.shape
        for y in range(0, h - 4, 2):
            for x in range(0, w - 4, 2):
                region = grid[y:y+5, x:x+5]
                if int((region == 8).sum()) >= 5 and int((region == 1).sum()) >= 3:
                    tx, ty = x // TILE_SIZE, y // TILE_SIZE
                    if (tx, ty) not in self._portal_tiles:
                        self._portal_tiles[(tx, ty)] = "portal"

    def _scan_modifiers_pixel(self, grid: np.ndarray) -> None:
        for ty in range(GRID_TILES_Y):
            for tx in range(GRID_TILES_X):
                region = grid[ty*TILE_SIZE:(ty+1)*TILE_SIZE, tx*TILE_SIZE:(tx+1)*TILE_SIZE]
                if int((region == 14).sum()) >= 3:
                    if (tx, ty) not in self._modifier_tiles:
                        self._modifier_tiles[(tx, ty)] = "green"

    # ------------------------------------------------------------------
    # FIX17: Prolog v4 integration
    # ------------------------------------------------------------------

    def _generate_prolog_facts(self, tile_grid, player_tile):
        lines = ["%% PrologReasoning6 KB"]
        lines.append(f"max_tile_x({GRID_TILES_X - 1}).")
        lines.append(f"max_tile_y({GRID_TILES_Y - 1}).")
        lines.append(f"tile_size({TILE_SIZE}).")
        for ty in range(GRID_TILES_Y):
            for tx in range(GRID_TILES_X):
                if tile_grid[ty, tx] == _TILE_WALL:
                    lines.append(f"wall({tx}, {ty}).")
        for (tx, ty), ptype in self._portal_tiles.items():
            lines.append(f"portal({tx}, {ty}, {ptype}).")
        for (tx, ty), mtype in self._modifier_tiles.items():
            lines.append(f"modifier({tx}, {ty}, {mtype}).")
        if self._had_modifier:
            lines.append("had_modifier(unknown).")
        if player_tile:
            lines.append(f"player({player_tile[0]}, {player_tile[1]}).")
            lines.append(f"explored({player_tile[0]}, {player_tile[1]}).")
        for (vx, vy) in self._visited_tiles:
            if 0 <= vx < GRID_TILES_X and 0 <= vy < GRID_TILES_Y:
                if (vx, vy) not in self._wall_tiles:
                    lines.append(f"explored({vx}, {vy}).")
        lines.append(f"level({self._best_levels}).")
        return "\n".join(lines)

    def _query_prolog(self, facts_block: str) -> Optional[int]:
        if not self._has_prolog or not ARC_RULES_V4_PL.exists():
            return None
        try:
            rules = ARC_RULES_V4_PL.read_text(encoding="utf-8")
            prog = f":- encoding(utf8).\n{rules}\n:- dynamic max_tile_x/1, max_tile_y/1, tile_size/1, wall/2, player/2.\n:- dynamic explored/2, portal/3, modifier/3, had_modifier/1.\n:- dynamic step_pickup/2, level/1, action_taken/3, known_floor/1.\n{facts_block}\n:- initialization(main).\n"
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pl", delete=False, encoding="utf-8") as f:
                f.write(prog)
                tmp = f.name
            r = subprocess.run([self._prolog_cmd, "-q", "-g", "main", "-t", "halt", tmp],
                               capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
            os.unlink(tmp)
            for line in r.stdout.split("\n"):
                line = line.strip()
                if line == "PLAYER_UNKNOWN":
                    return 0
                if line.startswith("NEXT_ACTION:"):
                    try:
                        n = int(line.split(":")[1])
                        if 1 <= n <= 6:
                            return n
                    except (ValueError, IndexError):
                        continue
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # FIX14: Anti-loop stuck detection
    # ------------------------------------------------------------------

    def _check_anti_loop(self, action_name: str) -> bool:
        self._action_history.append(action_name)
        if len(self._action_history) > 20:
            self._action_history.pop(0)
        if action_name == self._last_same_action:
            self._same_action_count += 1
        else:
            self._same_action_count = 0
            self._forced_alternation = False
        self._last_same_action = action_name
        if self._same_action_count >= 15:
            self._forced_alternation = True
            return True
        return False

    def _get_alternating_action(self) -> GameAction:
        acts = ["ACTION4", "ACTION3", "ACTION1", "ACTION2"]
        a = GameAction.from_name(acts[self._alternation_index % 4])
        self._alternation_index += 1
        return a

    # ------------------------------------------------------------------
    # Python navigation helpers
    # ------------------------------------------------------------------

    def _get_valid_moves(self, px, py):
        moves = []
        for i, (dx, dy) in enumerate(DIRS):
            nx, ny = px + dx, py + dy
            if 0 <= nx < GRID_TILES_X and 0 <= ny < GRID_TILES_Y:
                if (nx, ny) not in self._wall_tiles:
                    moves.append((i, DIR_ACTIONS[i], nx, ny))
        return moves

    def _bfs(self, sx, sy, ex, ey):
        if (sx, sy) == (ex, ey):
            return [(sx, sy)]
        q = deque([((sx, sy), [(sx, sy)])])
        v = {(sx, sy)}
        while q:
            (cx, cy), path = q.popleft()
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < GRID_TILES_X and 0 <= ny < GRID_TILES_Y:
                    if (nx, ny) == (ex, ey):
                        return path + [(nx, ny)]
                    if (nx, ny) not in v and (nx, ny) not in self._wall_tiles:
                        v.add((nx, ny))
                        q.append(((nx, ny), path + [(nx, ny)]))
        return []

    def _dir_to_action(self, px, py, target):
        dx, dy = target[0] - px, target[1] - py
        if dx == 1: return GameAction.ACTION4
        if dx == -1: return GameAction.ACTION3
        if dy == 1: return GameAction.ACTION2
        if dy == -1: return GameAction.ACTION1
        return GameAction.ACTION1

    def _choose_action_python(self, px, py):
        moves = self._get_valid_moves(px, py)
        if not moves:
            if self._pos_stack:
                target = self._pos_stack.pop()
                path = self._bfs(px, py, target[0], target[1])
                if len(path) >= 2:
                    return self._dir_to_action(px, py, path[1])
            return self._get_alternating_action()
        for _, act, nx, ny in moves:
            if (nx, ny) in self._portal_tiles or (nx, ny) in self._modifier_tiles:
                if self._interact_cooldown <= 0:
                    self._interact_cooldown = 3
                    return GameAction.ACTION5
        unexplored = [(i, a, nx, ny) for i, a, nx, ny in moves
                      if (nx, ny) not in self._visited_tiles]
        if unexplored:
            return random.choice(unexplored)[1]
        if len(moves) <= 2:
            self._corridor_probe_counter += 1
            if self._corridor_probe_counter >= 5:
                self._corridor_probe_counter = 0
                side = [(i, a, nx, ny) for i, a, nx, ny in moves if i >= 2]
                if side:
                    return random.choice(side)[1]
        if self._forced_alternation:
            self._forced_alternation = False
            return self._get_alternating_action()
        dc = self._direction_counter
        sm = sorted(moves, key=lambda m: dc.get(DIR_NAMES[m[0]], 0))
        c = random.choice(sm[:min(2, len(sm))])
        dc[DIR_NAMES[c[0]]] = dc.get(DIR_NAMES[c[0]], 0) + 1
        return c[1]

    @property
    def _direction_counter(self):
        if not hasattr(self, '_dir_counter'):
            self._dir_counter = {}
        return self._dir_counter

    # ------------------------------------------------------------------
    # AGENT INTERFACE
    # ------------------------------------------------------------------

    def is_done(self, frames, latest_frame):
        if latest_frame.state is GameState.WIN:
            return True
        if latest_frame.state is GameState.GAME_OVER:
            if latest_frame.levels_completed > self._best_levels:
                self._best_levels = latest_frame.levels_completed
                return False
            return True
        return False

    def choose_action(self, frames, latest_frame):
        self._frame_count += 1
        self._action_count += 1
        if self._interact_cooldown > 0:
            self._interact_cooldown -= 1
        if latest_frame.state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            self._clear_all_state()
            return GameAction.RESET

        grid = self._get_grid(latest_frame.frame)

        if latest_frame.levels_completed > self._best_levels:
            self._best_levels = latest_frame.levels_completed
            logger.info(f"=== LEVEL {self._best_levels}! ===")
            self._portal_tiles.clear()
            self._modifier_tiles.clear()
            self._wall_tiles.clear()
            self._visited_tiles.clear()
            self._had_modifier = False
            self._pos_stack.clear()
            self._backtrack_mode = False

        if self._prev_grid is not None:
            pg = np.where(self._prev_grid == 14)
            cg = np.where(grid == 14)
            if len(pg[0]) > 0 and len(cg[0]) == 0:
                self._had_modifier = True
            elif len(pg[0]) > len(cg[0]):
                self._had_modifier = True

        if not self._color_samples_taken:
            self._sample_colors(grid)

        tile_grid = self._build_tile_grid(grid)

        for ty in range(GRID_TILES_Y):
            for tx in range(GRID_TILES_X):
                if tile_grid[ty, tx] == _TILE_WALL:
                    self._wall_tiles.add((tx, ty))

        self._scan_portals_pixel(grid)
        self._scan_modifiers_pixel(grid)

        for ty in range(GRID_TILES_Y):
            for tx in range(GRID_TILES_X):
                v = tile_grid[ty, tx]
                if v == _TILE_PORTAL and (tx, ty) not in self._portal_tiles:
                    self._portal_tiles[(tx, ty)] = "portal"
                elif v == _TILE_MODIFIER and (tx, ty) not in self._modifier_tiles:
                    self._modifier_tiles[(tx, ty)] = "green"

        player_pixel = self._find_player(grid)
        if player_pixel:
            new_tile = self._pixel_to_tile(player_pixel[0], player_pixel[1])
            if self._player_tile is not None and new_tile == self._player_tile:
                self._consecutive_stuck += 1
            else:
                self._consecutive_stuck = 0
                if self._player_tile is not None and self._player_tile != new_tile:
                    self._pos_stack.append(self._player_tile)
                    if len(self._pos_stack) > 20:
                        self._pos_stack.pop(0)
            self._player_pixel = player_pixel
            self._player_tile = new_tile
            self._visited_tiles.add(new_tile)
        else:
            self._consecutive_stuck += 1

        self._prev_grid = grid

        if self._player_tile:
            px, py = self._player_tile
            for _, act, nx, ny in self._get_valid_moves(px, py):
                if (nx, ny) in self._portal_tiles or (nx, ny) in self._modifier_tiles:
                    if self._interact_cooldown <= 0:
                        self._interact_cooldown = 3
                        return GameAction.ACTION5

        if self._had_modifier and self._player_tile and self._portal_tiles:
            px, py = self._player_tile
            best, bd = None, 999
            for (tx, ty) in self._portal_tiles:
                d = abs(tx - px) + abs(ty - py)
                if d < bd:
                    bd, best = d, (tx, ty)
            if best and bd > 1:
                path = self._bfs(px, py, best[0], best[1])
                if len(path) >= 2:
                    a = self._dir_to_action(px, py, path[1])
                    a.reasoning = {"agent": "prolog6", "method": "portal_rush"}
                    self._check_anti_loop(a.name)
                    return a

        if self._has_prolog and self._player_tile and self._consecutive_stuck < 10:
            facts = self._generate_prolog_facts(tile_grid, self._player_tile)
            an = self._query_prolog(facts)
            if an is not None and an > 0:
                a = self._action_number(an)
                a.reasoning = {"agent": "prolog6", "method": "prolog_v4",
                               "tile": f"({self._player_tile[0]},{self._player_tile[1]})"}
                self._check_anti_loop(a.name)
                return a

        if self._player_tile:
            a = self._choose_action_python(self._player_tile[0], self._player_tile[1])
            a.reasoning = {"agent": "prolog6", "method": "adaptive"}
            self._check_anti_loop(a.name)
            return a

        return GameAction.ACTION1

    def _action_number(self, num):
        m = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
             4: GameAction.ACTION4, 5: GameAction.ACTION5, 6: GameAction.ACTION6}
        return m.get(num, GameAction.ACTION1)

    def cleanup(self, *args, **kwargs):
        if self._cleanup and hasattr(self, "recorder") and not self.is_playback:
            self.recorder.record({
                "agent_type": "prolog_reasoning6",
                "has_prolog": self._has_prolog,
                "actions_taken": self._action_count,
                "levels_completed": self._best_levels,
                "wall_colors": list(self._wall_colors),
                "floor_colors": list(self._floor_colors),
            })
        super().cleanup(*args, **kwargs)
