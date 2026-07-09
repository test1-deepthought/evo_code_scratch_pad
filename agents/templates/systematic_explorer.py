"""
SystematicExplorerAgent - ARC-AGI-3 Submission Agent

A meta-reasoning agent that systematically explores game environments,
discovers mechanics through hypothesis-driven experimentation, and
adapts its strategy to win.

Key features:
1. Phase-based exploration: systematic discovery of game mechanics
2. Hypothesis tracking: maintains and updates beliefs about game rules
3. Strategic adaptation: selects actions based on discovered patterns
4. Efficient execution: minimizes actions needed to win
5. Handles both simple (movement) and complex (click) actions
"""

import json
import logging
import math
import os
import textwrap
import time
from collections import defaultdict
from enum import Enum
from typing import Any, Optional

import openai
from arcengine import FrameData, GameAction, GameState
from openai import OpenAI as OpenAIClient

from ..agent import Agent

logger = logging.getLogger(__name__)


class ExplorationPhase(Enum):
    """Phases of systematic game exploration."""
    INITIAL_RESET = "initial_reset"
    DISCOVER_ACTIONS = "discover_actions"  # Try each action type
    MAP_GRID = "map_grid"                 # Map walkable area with movement
    FIND_GOAL = "find_goal"               # Find objective/win condition
    SOLVE = "solve"                       # Execute solution plan
    RECOVERY = "recovery"                 # Recover from failure/death


class ActionHypothesis:
    """Track what we know about a specific action's effects."""
    
    def __init__(self, action_name: str):
        self.action_name = action_name
        self.times_tried = 0
        self.times_changed_state = 0
        self.effects_observed: list[str] = []
        self.is_movement = False
        self.is_interaction = False
        self.last_result: Optional[str] = None
        
    def record_effect(self, before_frame, after_frame, description: str):
        """Record what happened when this action was used."""
        self.times_tried += 1
        self.effects_observed.append(description)
        self.last_result = description
        
        # Detect if this action causes grid changes (movement)
        if before_frame and before_frame.frame != after_frame.frame:
            self.times_changed_state += 1


class SystematicExplorerAgent(Agent):
    """
    A meta-reasoning agent that systematically explores games to discover
    mechanics and formulate winning strategies.
    """
    
    MAX_ACTIONS: int = 200  # Higher limit for exploration-heavy games
    DISCOVERY_ROUNDS: int = 5  # How many actions to try during discovery
    
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        
        # Exploration state
        self.phase = ExplorationPhase.INITIAL_RESET
        self.discovery_actions_tested: list[str] = []
        self.action_hypotheses: dict[str, ActionHypothesis] = {}
        
        # Grid memory
        self.known_grids: dict[str, list[list[list[int]]]] = {}
        self.movement_history: list[tuple[int, int, str]] = []  # (x, y, direction)
        self.last_image_hash: Optional[str] = None
        
        # Game model
        self.game_model = {
            "game_over_condition": None,
            "win_condition": None,
            "walkable_values": set(),
            "dangerous_values": set(),
            "important_values": set(),
            "action_effects": {},
            "known_mechanics": [],
        }
        
        # LLM integration
        self.client = OpenAIClient(api_key=os.environ.get("OPENAI_API_KEY", ""))
        self.llm_messages: list[dict[str, Any]] = []
        self.token_counter = 0
        
        # Player tracking
        self.player_position: Optional[tuple[int, int]] = None
        self.player_color = 4  # Default player color from template
        
        # Initialize action hypotheses
        for action in GameAction:
            name = action.name
            self.action_hypotheses[name] = ActionHypothesis(name)

    @property
    def name(self) -> str:
        return f"{super().name}.systematic_explorer"

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        """Decide if the game is complete."""
        return any([
            latest_frame.state is GameState.WIN,
        ])

    def choose_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Main decision-making method. Selects action based on current exploration phase."""
        
        # Handle initial reset
        if latest_frame.state in [GameState.NOT_PLAYED, GameState.GAME_OVER]:
            self.phase = ExplorationPhase.INITIAL_RESET
            action = GameAction.RESET
            action.reasoning = {"phase": self.phase.value, "reason": "Resetting game"}
            return action

        # On first real frame after reset, start discovery
        if self.phase == ExplorationPhase.INITIAL_RESET:
            self.phase = ExplorationPhase.DISCOVER_ACTIONS
            logger.info("Game reset complete. Starting action discovery phase.")
        
        # Analyze current frame for useful information
        self._analyze_frame(latest_frame)
        
        # Phase-based action selection
        return self._phase_based_action(frames, latest_frame)

    def _analyze_frame(self, frame: FrameData) -> None:
        """Analyze the current frame for useful information."""
        grid = frame.frame
        
        # Compute hash of current grid for change detection
        grid_str = str(grid)
        self.last_image_hash = grid_str[:100]  # Prefix hash
        
        # Scan for important values
        for layer_idx, layer in enumerate(grid):
            for row_idx, row in enumerate(layer):
                for col_idx, val in enumerate(row):
                    val_int = val if isinstance(val, int) else 0
                    if val_int > 0 and val_int < 15:
                        if val_int in {8, 10}:  # Walkable floor
                            self.game_model["walkable_values"].add(val_int)
                        elif val_int in {6, 7}:  # Often points/items
                            self.game_model["important_values"].add(val_int)
                        elif val_int > 10:  # Walls/obstacles
                            self.game_model["important_values"].add(val_int)
        
        # Try to detect player (commonly a 4x4 block of a specific color)
        # Look for contiguous blocks of non-background colors
        self._detect_player(grid)
    
    def _detect_player(self, grid: list) -> Optional[tuple[int, int, int, int]]:
        """Detect player position by looking for characteristic patterns."""
        # Player is often a multi-cell object. Scan for 2x2+ blocks.
        if not grid or not grid[0]:
            return None
            
        # Look for significant non-zero, non-wall areas
        # In many ARC-AGI games, the player is color 4 (dark gray)
        # or some unique identifiable object
        for layer in grid:
            for y in range(len(layer) - 1):
                for x in range(len(layer[0]) - 1):
                    # Check for 2x2 block of same color
                    cells = [layer[y][x], layer[y][x+1], 
                             layer[y+1][x], layer[y+1][x+1]]
                    if cells[0] == cells[1] == cells[2] == cells[3] and cells[0] not in {0, 10}:
                        self.player_color = cells[0]
                        self.player_position = (x, y)
                        return (x, y, x+1, y+1)
        return None

    def _phase_based_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Select action based on current exploration phase."""
        
        if self.phase == ExplorationPhase.DISCOVER_ACTIONS:
            return self._discover_actions_phase(frames, latest_frame)
        elif self.phase == ExplorationPhase.MAP_GRID:
            return self._map_grid_phase(frames, latest_frame)
        elif self.phase == ExplorationPhase.FIND_GOAL:
            return self._find_goal_phase(frames, latest_frame)
        elif self.phase == ExplorationPhase.SOLVE:
            return self._solve_phase(frames, latest_frame)
        elif self.phase == ExplorationPhase.RECOVERY:
            return self._recovery_phase(frames, latest_frame)
        
        # Fallback
        return GameAction.ACTION1

    def _discover_actions_phase(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Try each action to discover what it does."""
        
        # Actions to test in order
        test_order = ["ACTION1", "ACTION2", "ACTION3", "ACTION4", 
                      "ACTION5", "ACTION6"]
        
        for action_name in test_order:
            if action_name not in self.discovery_actions_tested:
                self.discovery_actions_tested.append(action_name)
                action = GameAction.from_name(action_name)
                
                if action_name == "ACTION6":
                    # Try ACTION6 at the center of the grid
                    action.set_data({"x": 32, "y": 32})
                    action.reasoning = {
                        "phase": "discovery",
                        "testing": "ACTION6 at center (32,32)"
                    }
                else:
                    action.reasoning = {
                        "phase": "discovery",
                        "testing": f"Testing {action_name}"
                    }
                
                logger.info(f"Discovery: testing {action_name}")
                return action
        
        # All actions tested, move to grid mapping
        self.phase = ExplorationPhase.MAP_GRID
        logger.info("Action discovery complete. Moving to grid mapping.")
        return self._map_grid_phase(frames, latest_frame)

    def _map_grid_phase(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Systematically explore the grid to understand its structure."""
        
        # Use movement actions (ACTION1-4) to explore
        # Check if we can move in different directions
        state = latest_frame.state
        
        # Try each direction in sequence
        directions = ["ACTION1", "ACTION2", "ACTION3", "ACTION4"]
        
        last_action_name = None
        if len(frames) > 1:
            last_frame = frames[-2]
            if hasattr(last_frame, 'action_input') and last_frame.action_input:
                last_action_name = last_frame.action_input.id.name
        
        # Determine if last action succeeded (grid changed)
        grid_changed = self._grid_changed(frames)
        
        # If stuck, try a different direction
        if not grid_changed and last_action_name in directions:
            # Try next direction
            idx = directions.index(last_action_name)
            next_idx = (idx + 1) % len(directions)
            chosen = directions[next_idx]
        else:
            # Continue current exploration direction cycle
            chosen = directions[len(self.movement_history) % len(directions)]
        
        action = GameAction.from_name(chosen)
        action.reasoning = {
            "phase": "mapping",
            "direction": chosen,
            "grid_changed": grid_changed,
            "action_count": self.action_counter
        }
        
        self.movement_history.append((0, 0, chosen))
        return action

    def _find_goal_phase(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Use LLM reasoning to understand the goal and plan."""
        
        # If we have an LLM, use it for strategic reasoning
        return self._llm_guided_action(frames, latest_frame)

    def _solve_phase(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Execute planned solution with LLM guidance."""
        return self._llm_guided_action(frames, latest_frame)

    def _recovery_phase(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Recover from game over or getting stuck."""
        
        if latest_frame.state is GameState.GAME_OVER:
            # Reset and try again with more knowledge
            action = GameAction.RESET
            action.reasoning = {
                "phase": "recovery",
                "reason": "Game over - resetting with knowledge"
            }
            self.phase = ExplorationPhase.INITIAL_RESET
            return action
        
        # If not game over but stuck, go back to discovery
        self.phase = ExplorationPhase.DISCOVER_ACTIONS
        return self._discover_actions_phase(frames, latest_frame)

    def _llm_guided_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Use LLM to analyze the game state and choose an action."""
        
        try:
            # Build prompt with current game context
            prompt = self._build_llm_prompt(frames, latest_frame)
            
            response = self.client.chat.completions.create(
                model="o4-mini",
                messages=[
                    {
                        "role": "system",
                        "content": textwrap.dedent("""\
                        You are an agent playing an unknown dynamic game.
                        Analyze the grid state, identify patterns, and choose
                        exactly one action. Consider:
                        
                        1. What changed after your last action?
                        2. What patterns do you see in the grid?
                        3. What might the objective be?
                        4. What action would make progress?
                        
                        Respond with JSON:
                        {"action": "ACTION_NAME", "reasoning": "your analysis", 
                         "x": null, "y": null}
                        For ACTION6, provide x,y coordinates (0-63).
                        For other actions, set x and y to null.
                        """)
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=500,
            )
            
            # Parse response
            content = response.choices[0].message.content
            if not content:
                return self._fallback_action()
            
            try:
                decision = json.loads(content)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response: {content}")
                return self._fallback_action()
            
            action_name = decision.get("action", "ACTION1")
            reasoning = decision.get("reasoning", "")
            x = decision.get("x")
            y = decision.get("y")
            
            try:
                action = GameAction.from_name(action_name)
            except (ValueError, KeyError):
                logger.warning(f"Invalid action name: {action_name}")
                return self._fallback_action()
            
            if action.is_complex() and x is not None and y is not None:
                action.set_data({"x": int(x), "y": int(y)})
            
            action.reasoning = {
                "source": "llm",
                "analysis": reasoning,
                "phase": self.phase.value
            }
            
            return action
            
        except (openai.RateLimitError, openai.APIError) as e:
            logger.warning(f"LLM API error: {e}. Using fallback.")
            return self._fallback_action()
        except Exception as e:
            logger.error(f"Unexpected LLM error: {e}")
            return self._fallback_action()

    def _build_llm_prompt(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> str:
        """Build a comprehensive prompt for the LLM."""
        
        # Get grid summary
        grid_preview = self._grid_to_text(latest_frame.frame)
        
        # Get change history
        recent_changes = self._get_recent_changes(frames)
        
        return textwrap.dedent(f"""\
# Game State
State: {latest_frame.state.name}
Levels Completed: {latest_frame.levels_completed}
Action Count: {self.action_counter}

# Current Grid
{grid_preview}

# Recent History
{recent_changes}

# Current Phase
{self.phase.value}

# Available Actions
- RESET: Start/restart
- ACTION1: Up/North
- ACTION2: Down/South  
- ACTION3: Left/West
- ACTION4: Right/East
- ACTION5: Interact/Enter
- ACTION6: Click at (x,y) coordinates

# What I've Learned So Far
{self._summarize_knowledge()}

# Task
Analyze the current state, reason about what's happening,
and choose the best action to make progress toward winning.
""")

    def _grid_to_text(self, grid: list) -> str:
        """Convert grid to compact text representation."""
        if not grid or not grid[0]:
            return "Empty grid"
        
        # Take first layer for preview
        layer = grid[0]
        height = len(layer)
        width = len(layer[0])
        
        # Summarize grid: count each value and show structure
        value_counts = defaultdict(int)
        for row in layer:
            for val in row:
                value_counts[val] += 1
        
        summary = f"Grid size: {width}x{height}\n"
        summary += f"Cell values: {dict(sorted(value_counts.items()))}\n"
        
        # Show a compact representation (first and last few rows)
        summary += "Top rows:\n"
        for row in layer[:4]:
            summary += f"  {row[:16]}...\n"
        
        if height > 8:
            summary += "  ...\n"
            summary += "Bottom rows:\n"
            for row in layer[-4:]:
                summary += f"  {row[:16]}...\n"
        
        return summary

    def _get_recent_changes(self, frames: list[FrameData]) -> str:
        """Get description of recent changes between frames."""
        if len(frames) < 3:
            return "Game just started."
        
        changes = []
        for i in range(max(0, len(frames) - 6), len(frames) - 1):
            before = frames[i].frame
            after = frames[i+1].frame
            
            # Check if grid changed
            if before != after:
                action_name = "UNKNOWN"
                if hasattr(frames[i+1], 'action_input') and frames[i+1].action_input:
                    action_name = frames[i+1].action_input.id.name
                changes.append(f"  After {action_name}: Grid changed")
            else:
                action_name = "UNKNOWN"
                if hasattr(frames[i+1], 'action_input') and frames[i+1].action_input:
                    action_name = frames[i+1].action_input.id.name
                changes.append(f"  After {action_name}: No change (blocked)")
        
        if not changes:
            return "No significant changes observed."
        
        return "Recent frames:\n" + "\n".join(changes[-5:])

    def _summarize_knowledge(self) -> str:
        """Summarize what the agent has learned so far."""
        knowledge = []
        
        for name, hypo in self.action_hypotheses.items():
            if hypo.times_tried > 0:
                knowledge.append(
                    f"  {name}: tried {hypo.times_tried}x, "
                    f"changed state {hypo.times_changed_state}x"
                )
        
        if self.game_model["walkable_values"]:
            knowledge.append(
                f"  Walkable values: {self.game_model['walkable_values']}"
            )
        
        if self.game_model["important_values"]:
            knowledge.append(
                f"  Important values: {self.game_model['important_values']}"
            )
        
        if self.player_position:
            knowledge.append(
                f"  Player detected near ({self.player_position[0]}, "
                f"{self.player_position[1]}) with color {self.player_color}"
            )
        
        if not knowledge:
            return "  Nothing learned yet."
        
        return "\n".join(knowledge)

    def _grid_changed(self, frames: list[FrameData]) -> bool:
        """Check if the latest action caused a grid change."""
        if len(frames) < 2:
            return False
        return frames[-1].frame != frames[-2].frame

    def _fallback_action(self) -> GameAction:
        """Select a fallback action when LLM is unavailable."""
        # Cycle through actions
        cycle = ["ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5"]
        idx = self.action_counter % len(cycle)
        action = GameAction.from_name(cycle[idx])
        action.reasoning = {"source": "fallback", "cycle_index": idx}
        return action
